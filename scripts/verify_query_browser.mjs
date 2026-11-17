import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import os from "node:os";

const CHROME_PATH = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe";
const PORT = 9222;
const tempUserData = path.join(os.tmpdir(), `chrome_qa_${Date.now()}`);

console.log("Launching Headless Chrome on port", PORT, "...");
const chrome = spawn(
  CHROME_PATH,
  [
    `--remote-debugging-port=${PORT}`,
    "--headless=new",
    "--disable-gpu",
    "--no-first-run",
    "--no-default-browser-check",
    `--user-data-dir=${tempUserData}`,
    "about:blank",
  ],
  { stdio: "ignore" }
);

function cleanup() {
  try {
    chrome.kill();
  } catch (_) {}
  try {
    fs.rmSync(tempUserData, { recursive: true, force: true });
  } catch (_) {}
}

process.on("exit", cleanup);
process.on("SIGINT", () => { cleanup(); process.exit(1); });
process.on("SIGTERM", () => { cleanup(); process.exit(1); });

async function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function waitForDebugPort() {
  for (let i = 0; i < 30; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${PORT}/json/version`);
      if (res.ok) return await res.json();
    } catch (_) {}
    await sleep(500);
  }
  throw new Error("Chrome debug port failed to become available within 15 seconds.");
}

async function main() {
  const versionInfo = await waitForDebugPort();
  console.log("Connected to Chrome:", versionInfo["Browser"]);

  const targetsRes = await fetch(`http://127.0.0.1:${PORT}/json/list`);
  const targets = await targetsRes.json();
  const pageTarget = targets.find((t) => t.type === "page") || targets[0];
  if (!pageTarget || !pageTarget.webSocketDebuggerUrl) {
    throw new Error("No page target with webSocketDebuggerUrl found.");
  }

  console.log("Connecting WebSocket to page target:", pageTarget.webSocketDebuggerUrl);
  const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);

  let msgId = 0;
  const pendingRequests = new Map();
  const consoleMessages = [];
  const consoleErrors = [];

  function sendCommand(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++msgId;
      pendingRequests.set(id, { resolve, reject, method });
      ws.send(JSON.stringify({ id, method, params }));
    });
  }

  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      if (msg.id && pendingRequests.has(msg.id)) {
        const { resolve, reject, method } = pendingRequests.get(msg.id);
        pendingRequests.delete(msg.id);
        if (msg.error) {
          reject(new Error(`CDP [${method}] failed: ${msg.error.message}`));
        } else {
          resolve(msg.result);
        }
      } else if (msg.method === "Runtime.consoleAPICalled") {
        const type = msg.params.type;
        const text = (msg.params.args || []).map((a) => a.value || JSON.stringify(a)).join(" ");
        consoleMessages.push(`[${type}] ${text}`);
        if (type === "error") {
          consoleErrors.push(text);
        }
      } else if (msg.method === "Runtime.exceptionThrown") {
        const desc = msg.params.exceptionDetails?.text || JSON.stringify(msg.params);
        consoleErrors.push(`Exception: ${desc}`);
      }
    } catch (e) {
      console.error("WS parse error:", e);
    }
  };

  await sendCommand("Page.enable");
  await sendCommand("Runtime.enable");

  console.log("Navigating to http://localhost:8000 ...");
  await sendCommand("Page.navigate", { url: "http://localhost:8000" });
  await sleep(2000);

  // Check that page is loaded
  const titleRes = await sendCommand("Runtime.evaluate", {
    expression: "document.title",
    returnByValue: true,
  });
  console.log("Document Title:", titleRes.result.value);

  // Check initial #query-results
  const initialCheck = await sendCommand("Runtime.evaluate", {
    expression: `(() => {
      const el = document.getElementById("query-results");
      return el ? el.innerText.trim() : null;
    })()`,
    returnByValue: true,
  });
  console.log("Initial #query-results text:", initialCheck.result.value);

  // Submit Codebase Query
  console.log("Submitting query: 'How does the Neo4jClient connect to the database?'");
  await sendCommand("Runtime.evaluate", {
    expression: `(() => {
      const input = document.getElementById("query-input");
      input.value = "How does the Neo4jClient connect to the database?";
      const btn = document.getElementById("btn-run-query");
      btn.click();
    })()`,
  });

  // Wait for loading to start and button to show spinner
  await sleep(1000);
  const loadingCheck = await sendCommand("Runtime.evaluate", {
    expression: `(() => {
      const btn = document.getElementById("btn-run-query");
      const results = document.getElementById("query-results");
      return {
        btnDisabled: btn.disabled,
        btnText: btn.innerText.trim(),
        hasSpinner: results.innerHTML.includes("spinner")
      };
    })()`,
    returnByValue: true,
  });
  console.log("Loading state verified:", loadingCheck.result.value);

  // Wait for answer to be rendered (poll up to 60s)
  console.log("Waiting for Graph RAG execution and answer rendering...");
  let answered = false;
  let finalState = null;

  for (let i = 0; i < 60; i++) {
    await sleep(1000);
    const check = await sendCommand("Runtime.evaluate", {
      expression: `(() => {
        const btn = document.getElementById("btn-run-query");
        const answerText = document.getElementById("answer-text");
        const badge = document.getElementById("validation-badge");
        const sources = Array.from(document.querySelectorAll(".source-pill")).map(p => p.innerText.trim());
        const results = document.getElementById("query-results");
        return {
          btnDisabled: btn ? btn.disabled : true,
          btnText: btn ? btn.innerText.trim() : "",
          hasAnswerText: !!answerText,
          answerLength: answerText ? answerText.innerText.length : 0,
          answerPreview: answerText ? answerText.innerText.slice(0, 300) : "",
          badgeText: badge ? badge.innerText.trim() : null,
          badgeClass: badge ? badge.className : null,
          sourcesCount: sources.length,
          sources: sources,
          resultsInnerLength: results ? results.innerHTML.length : 0
        };
      })()`,
      returnByValue: true,
    });

    finalState = check.result.value;
    if (finalState && finalState.hasAnswerText && !finalState.btnDisabled) {
      answered = true;
      break;
    }
  }

  if (!answered) {
    console.error("TIMEOUT: Answer did not appear within 60s. Final state:", finalState);
    cleanup();
    process.exit(1);
  }

  console.log("\n================ LIVE BROWSER VERIFICATION RESULT ================");
  console.log("1. Answer Visible in DOM:", finalState.hasAnswerText);
  console.log("2. Answer Character Length:", finalState.answerLength);
  console.log("3. Answer Preview:\n", finalState.answerPreview);
  console.log("4. Groundedness Badge:", finalState.badgeText);
  console.log("5. Badge CSS Class:", finalState.badgeClass);
  console.log("6. Verified Citations Count:", finalState.sourcesCount);
  console.log("7. Cited Sources:", finalState.sources);
  console.log("8. Button Disabled State:", finalState.btnDisabled);
  console.log("9. Button Final Label:", finalState.btnText);
  console.log("10. Console Errors Count:", consoleErrors.length);
  if (consoleErrors.length > 0) {
    console.log("Console Errors:", consoleErrors);
  }

  // Capture screenshot of the verified page
  const screenshotRes = await sendCommand("Page.captureScreenshot", { format: "png" });
  fs.writeFileSync("browser_query_verified.png", Buffer.from(screenshotRes.data, "base64"));
  console.log("Saved full verification screenshot to: browser_query_verified.png");

  // Assertions
  if (finalState.answerLength < 100) {
    throw new Error(`Answer length too short (${finalState.answerLength} chars).`);
  }
  if (!finalState.badgeText || !finalState.badgeText.includes("Grounded Evidence Validated")) {
    throw new Error(`Grounded Evidence badge missing or incorrect: ${finalState.badgeText}`);
  }
  if (finalState.sourcesCount === 0) {
    throw new Error("Zero source citations displayed.");
  }
  if (finalState.btnDisabled) {
    throw new Error("Button loading state did not reset.");
  }
  if (finalState.btnText !== "Run Codebase Query") {
    throw new Error(`Button text expected 'Run Codebase Query', got '${finalState.btnText}'`);
  }
  if (consoleErrors.length > 0) {
    throw new Error(`JavaScript errors occurred during query execution: ${consoleErrors.join("; ")}`);
  }

  console.log("\n>>> LIVE BROWSER VERIFICATION SUCCEEDED 100%! <<<\n");
  cleanup();
  process.exit(0);
}

main().catch((err) => {
  console.error("FATAL BROWSER TEST ERROR:", err);
  cleanup();
  process.exit(1);
});
