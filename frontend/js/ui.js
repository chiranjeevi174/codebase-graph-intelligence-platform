/**
 * Main UI Controller - Coordinates layout, tabs, modals, sidebar, tooltips, and repository controls.
 * Implements enterprise-grade source inspection, safe node property rendering, interactive tooltips,
 * and fullscreen graph inspection.
 */

import { fetchGraphData, fetchHealthStatus, fetchRepositories, fetchSourceCode, ingestRepository } from "./api.js";
import { initDiffView } from "./diff.js";
import {
  closeGraphFullscreen,
  fsResetZoom,
  fsZoomIn,
  fsZoomOut,
  highlightPath,
  initGraphVisualization,
  openGraphFullscreen,
  resetGraphZoom,
  updateGraphData,
  zoomIn,
  zoomOut,
} from "./graph.js";
import { initImpactView } from "./impact.js";
import { initPRView } from "./pr.js";
import { initQueryView, renderRepositorySuggestions } from "./query.js";
import { state } from "./state.js";

export function initUI() {
  initTabs();
  initRepositoryControls();
  initModalListeners();
  initGraphControls();
  initTooltips();

  initQueryView();
  initImpactView();
  initDiffView();
  initPRView();

  // Subscribe to state events
  state.subscribe((event, data) => handleStateEvent(event, data));

  // Initial data load
  refreshHealth();
  refreshRepositories();

  // Initialize graph
  setTimeout(() => {
    initGraphVisualization();
    loadCurrentRepoGraph();
  }, 200);
}

function initTabs() {
  const tabs = document.querySelectorAll(".nav-tab");
  const views = document.querySelectorAll(".workspace-view");

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const tabName = tab.dataset.tab;
      tabs.forEach((t) => t.classList.remove("active"));
      views.forEach((v) => v.classList.remove("active"));

      tab.classList.add("active");
      const targetView = document.getElementById(`view-${tabName}`);
      if (targetView) targetView.classList.add("active");

      state.setTab(tabName);
    });
  });
}

function initRepositoryControls() {
  const repoSelect = document.getElementById("repo-select");
  const ingestBtn = document.getElementById("btn-ingest-repo");

  if (repoSelect) {
    repoSelect.addEventListener("change", (e) => {
      state.setRepository(e.target.value);
    });
  }

  if (ingestBtn) {
    ingestBtn.addEventListener("click", async () => {
      const pathInput = document.getElementById("ingest-path-input");
      const urlInput = document.getElementById("ingest-url-input");
      const branchInput = document.getElementById("ingest-branch-input");
      const forceInput = document.getElementById("ingest-force-input");

      const repoPath = pathInput ? pathInput.value.trim() : "";
      const repoUrl = urlInput ? urlInput.value.trim() : "";
      const branch = branchInput ? branchInput.value.trim() : "";
      const force = forceInput ? forceInput.checked : false;

      if (!repoPath && !repoUrl) {
        alert("Please specify a local repository directory path or GitHub URL.");
        return;
      }

      ingestBtn.disabled = true;
      ingestBtn.innerHTML = `<span class="spinner"></span> Ingesting Repository...`;

      try {
        const payload = {
          repository_path: repoPath || null,
          repository_url: repoUrl || null,
          branch: branch || null,
          force: force,
        };
        const result = await ingestRepository(payload);
        alert(`Ingestion Successful!\nRepository ID: ${result.repository_id}\nFiles Discovered: ${result.files_discovered || result.files_processed}\nFiles Processed: ${result.files_processed}\nSymbols Extracted: ${result.symbols_extracted}\nRelationships: ${result.relationships_extracted}`);
        await refreshRepositories();
        state.setRepository(result.repository_id);
      } catch (err) {
        alert(`Ingestion Failed: ${err.message}`);
      } finally {
        ingestBtn.disabled = false;
        ingestBtn.innerHTML = `Ingest Repository`;
      }
    });
  }
}

function initGraphControls() {
  const btnZoomIn = document.getElementById("btn-zoom-in");
  const btnZoomOut = document.getElementById("btn-zoom-out");
  const btnReset = document.getElementById("btn-zoom-reset");
  const btnFullscreen = document.getElementById("btn-zoom-fullscreen");

  const btnCloseFs = document.getElementById("btn-close-fullscreen");
  const btnFsZoomIn = document.getElementById("btn-fs-zoom-in");
  const btnFsZoomOut = document.getElementById("btn-fs-zoom-out");
  const btnFsReset = document.getElementById("btn-fs-zoom-reset");

  if (btnZoomIn) btnZoomIn.addEventListener("click", () => zoomIn());
  if (btnZoomOut) btnZoomOut.addEventListener("click", () => zoomOut());
  if (btnReset) btnReset.addEventListener("click", () => resetGraphZoom());
  if (btnFullscreen) btnFullscreen.addEventListener("click", () => openGraphFullscreen());

  if (btnCloseFs) btnCloseFs.addEventListener("click", () => closeGraphFullscreen());
  if (btnFsZoomIn) btnFsZoomIn.addEventListener("click", () => fsZoomIn());
  if (btnFsZoomOut) btnFsZoomOut.addEventListener("click", () => fsZoomOut());
  if (btnFsReset) btnFsReset.addEventListener("click", () => fsResetZoom());
}

function initModalListeners() {
  const modal = document.getElementById("source-modal");
  const closeBtn = document.getElementById("btn-close-modal");

  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => {
      modal.classList.remove("active");
    });
  }

  if (modal) {
    modal.addEventListener("click", (e) => {
      if (e.target === modal) {
        modal.classList.remove("active");
      }
    });
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && modal && modal.classList.contains("active")) {
      modal.classList.remove("active");
    }
  });
}

/**
 * Reusable Floating Tooltip Design System.
 * Works seamlessly with dynamically created elements via robust event delegation.
 */
function initTooltips() {
  const tooltipEl = document.getElementById("global-tooltip");
  const titleEl = document.getElementById("tooltip-title");
  const bodyEl = document.getElementById("tooltip-body");

  if (!tooltipEl || !titleEl || !bodyEl) return;

  let currentTarget = null;

  document.addEventListener("mouseover", (e) => {
    const target = e.target.closest("[data-tooltip-title], [data-tooltip-body]");
    if (!target) return;

    currentTarget = target;
    const title = target.getAttribute("data-tooltip-title") || "";
    const body = target.getAttribute("data-tooltip-body") || "";

    if (!title && !body) return;

    titleEl.textContent = title;
    titleEl.style.display = title ? "block" : "none";
    bodyEl.textContent = body;
    bodyEl.style.display = body ? "block" : "none";

    tooltipEl.style.display = "block";
    positionTooltip(target, tooltipEl);
  });

  document.addEventListener("mouseout", (e) => {
    if (!currentTarget) return;
    const leavingTarget = e.target.closest("[data-tooltip-title], [data-tooltip-body]");
    const enteringTarget = e.relatedTarget ? e.relatedTarget.closest("[data-tooltip-title], [data-tooltip-body]") : null;

    if (leavingTarget === currentTarget && enteringTarget !== currentTarget) {
      tooltipEl.style.display = "none";
      currentTarget = null;
    }
  });

  document.addEventListener("mousemove", (e) => {
    if (currentTarget && tooltipEl.style.display === "block") {
      positionTooltip(currentTarget, tooltipEl);
    }
  });
}

function positionTooltip(target, tooltip) {
  const rect = target.getBoundingClientRect();
  const tipWidth = tooltip.offsetWidth || 240;
  const tipHeight = tooltip.offsetHeight || 60;

  let left = rect.left + rect.width / 2 - tipWidth / 2;
  let top = rect.top - tipHeight - 8;

  // Viewport bounds detection
  if (left < 12) left = 12;
  if (left + tipWidth > window.innerWidth - 12) {
    left = window.innerWidth - tipWidth - 12;
  }
  if (top < 10) {
    top = rect.bottom + 8; // flip below if not enough room on top
  }

  tooltip.style.left = `${Math.round(left)}px`;
  tooltip.style.top = `${Math.round(top)}px`;
}

async function refreshHealth() {
  const badge = document.getElementById("health-badge");
  const llmNameEl = document.getElementById("model-llm-name");
  const embNameEl = document.getElementById("model-emb-name");
  const llmBadge = document.getElementById("model-llm-badge");
  const embBadge = document.getElementById("model-emb-badge");

  try {
    const health = await fetchHealthStatus();
    state.setHealth(health);

    const llmProvider = health.llm_provider || "OpenAI";
    const embModel = health.embedding_model || "BAAI/bge-small-en-v1.5";

    if (badge) {
      badge.className = "status-badge";
      badge.innerHTML = `<span class="status-dot"></span> System Online`;
      badge.setAttribute("data-tooltip-title", "System Status: Online");
      badge.setAttribute(
        "data-tooltip-body",
        "FastAPI backend, Neo4j Graph database, and Qdrant vector retrieval services are connected and healthy."
      );
    }

    if (llmNameEl) llmNameEl.textContent = llmProvider;
    if (embNameEl) embNameEl.textContent = embModel;

    if (llmBadge) {
      llmBadge.setAttribute("data-tooltip-title", `Language Model: ${llmProvider}`);
      llmBadge.setAttribute(
        "data-tooltip-body",
        "Used as the language model for understanding code-related questions and generating grounded answers from retrieved repository evidence."
      );
    }

    if (embBadge) {
      embBadge.setAttribute("data-tooltip-title", `Embedding Model: ${embModel}`);
      embBadge.setAttribute(
        "data-tooltip-body",
        "Used to convert code and text into embeddings so semantically relevant repository content can be retrieved from Qdrant."
      );
    }
  } catch (err) {
    if (badge) {
      badge.className = "status-badge warning";
      badge.innerHTML = `<span class="status-dot"></span> System Offline`;
      badge.setAttribute("data-tooltip-title", "System Error");
      badge.setAttribute("data-tooltip-body", `Unable to establish connection to backend API: ${err.message}`);
    }
  }
}

async function refreshRepositories() {
  const select = document.getElementById("repo-select");
  const listContainer = document.getElementById("repo-list-container");

  try {
    const repos = await fetchRepositories();
    state.setRepositories(repos);

    if (select) {
      select.innerHTML = "";
      const defaultOptions = [
        { id: "sample_repo", name: "Sample Repo (Python/FastAPI)" },
        { id: "multi_language_repo", name: "Multi-Language Repo (Polyglot)" },
        { id: "diff_repo", name: "Diff Repo (Git History)" },
      ];

      const allReposMap = new Map();
      defaultOptions.forEach((o) => allReposMap.set(o.id, o.name));
      repos.forEach((r) => allReposMap.set(r.repository_id, `${r.name} (${r.repository_id})`));

      allReposMap.forEach((name, id) => {
        const opt = document.createElement("option");
        opt.value = id;
        opt.textContent = name;
        if (id === state.selectedRepository) opt.selected = true;
        select.appendChild(opt);
      });
    }

    if (listContainer) {
      const defaultList = [
        { name: "sample_repo", files_processed: 12, symbols_extracted: 64, status: "indexed" },
        { name: "multi_language_repo", files_processed: 28, symbols_extracted: 142, status: "indexed" },
        { name: "diff_repo", files_processed: 8, symbols_extracted: 45, status: "indexed" },
      ];

      const displayList = repos.length > 0 ? repos : defaultList;

      listContainer.innerHTML = displayList.map((r) => {
        const repoName = r.name || r.repository_id || "repository";
        const filesCount = r.files_processed != null ? r.files_processed : (r.files_discovered || 0);
        const symbolsCount = r.symbols_extracted != null ? r.symbols_extracted : 0;

        return `
          <div class="repo-card-item">
            <div class="repo-card-top">
              <span class="repo-card-name" data-tooltip-title="Full Repository Name" data-tooltip-body="${escapeAttr(repoName)}" title="${escapeAttr(repoName)}">
                ${escapeHtml(repoName)}
              </span>
              <span class="tag tag-emerald">Indexed</span>
            </div>
            <div class="repo-card-stats">
              <span class="stat-item" data-tooltip-title="Files Indexed" data-tooltip-body="Number of source files discovered, parsed by Tree-sitter, and indexed into the platform.">
                📄 Files: ${filesCount}
              </span>
              <span class="stat-divider">•</span>
              <span class="stat-item" data-tooltip-title="Symbols Extracted" data-tooltip-body="Number of meaningful code entities extracted (classes, functions, methods, API endpoints, contracts).">
                🏷️ Symbols: ${symbolsCount}
              </span>
            </div>
          </div>
        `;
      }).join("");
    }
  } catch (err) {
    console.warn("Error fetching repositories list:", err);
  }
}

async function loadCurrentRepoGraph() {
  const repoId = state.selectedRepository || "sample_repo";
  try {
    const data = await fetchGraphData(repoId, 150);
    state.setGraphData(data);
    updateGraphData(data);
  } catch (err) {
    console.warn("Failed loading graph summary:", err);
  }
}

function handleStateEvent(event, data) {
  if (event === "repo_changed") {
    loadCurrentRepoGraph();
  } else if (event === "node_selected") {
    renderRightPanelNodeDetails(data);
  } else if (event === "source_selected") {
    openSourceModal(data);
  }
}

/**
 * Format any value safely into string representation without ever returning [object Object].
 */
function safeProp(val, fallback = "—") {
  if (val === null || val === undefined || val === "") return fallback;
  if (typeof val === "string" || typeof val === "number" || typeof val === "boolean") {
    const str = String(val).trim();
    return str || fallback;
  }
  if (Array.isArray(val)) {
    if (val.length === 0) return fallback;
    return val.map((v) => safeProp(v, "")).filter(Boolean).join(", ") || fallback;
  }
  if (typeof val === "object") {
    if (val.qualified_name || val.name) return String(val.qualified_name || val.name);
    if (val.file_path) return String(val.file_path);
    try {
      return JSON.stringify(val);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

/**
 * Render Graph Inspector details ensuring zero [object Object] anomalies.
 */
function renderRightPanelNodeDetails(node) {
  const panel = document.getElementById("node-details-container");
  if (!panel) return;

  if (!node) {
    panel.innerHTML = `
      <div class="empty-inspector">
        <span class="inspector-icon">🎯</span>
        <p>Click any graph node on the canvas to inspect symbol properties, qualified name, line ranges, and source code links.</p>
      </div>
    `;
    return;
  }

  const displayName = safeProp(node.fullName || node.name || node.qualifiedName || node.id, "Selected Symbol");
  const nodeType = safeProp(node.symbolType || node.label, "Symbol");
  const qualifiedName = safeProp(node.qualifiedName || node.name, "—");
  const filePath = safeProp(node.filePath, "—");
  const startLine = typeof node.startLine === "number" ? node.startLine : 1;
  const endLine = typeof node.endLine === "number" ? node.endLine : startLine;
  const lineRangeStr = filePath !== "—" ? `L${startLine} - L${endLine}` : "—";
  const language = safeProp(node.language, "—");

  panel.innerHTML = `
    <div class="card inspector-card">
      <div class="card-title">
        <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;" title="${escapeAttr(displayName)}">${escapeHtml(displayName)}</span>
        <span class="tag tag-blue">${escapeHtml(nodeType)}</span>
      </div>
      <table class="kv-table">
        <tr>
          <td class="kv-key">Node Type</td>
          <td class="kv-val">${escapeHtml(nodeType)}</td>
        </tr>
        <tr>
          <td class="kv-key">Qualified Name</td>
          <td class="kv-val" style="word-break:break-all;">${escapeHtml(qualifiedName)}</td>
        </tr>
        <tr>
          <td class="kv-key">File Path</td>
          <td class="kv-val">
            ${filePath !== "—" 
              ? `<a href="#" id="link-open-file" style="color:var(--accent-blue); text-decoration:underline; cursor:pointer;" title="Click to open source code">${escapeHtml(filePath)}</a>` 
              : "—"}
          </td>
        </tr>
        <tr>
          <td class="kv-key">Line Range</td>
          <td class="kv-val">${escapeHtml(lineRangeStr)}</td>
        </tr>
        <tr>
          <td class="kv-key">Language</td>
          <td class="kv-val">${escapeHtml(language)}</td>
        </tr>
      </table>
    </div>
  `;

  const link = document.getElementById("link-open-file");
  if (link && filePath !== "—") {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      openSourceModal(filePath, startLine, endLine);
    });
  }
}

/**
 * Open Source Code Viewer Modal and highlight relevant lines.
 */
export async function openSourceModal(sourceParam, overrideStart = null, overrideEnd = null) {
  const modal = document.getElementById("source-modal");
  const modalTitle = document.getElementById("modal-file-title");
  const codeView = document.getElementById("modal-code-content");
  const langBadge = document.getElementById("modal-lang-badge");
  const linesBadge = document.getElementById("modal-lines-badge");

  if (!modal || !codeView) return;

  let filePath = "";
  let startLine = overrideStart;
  let endLine = overrideEnd;

  if (typeof sourceParam === "string") {
    filePath = sourceParam.trim();
    // Parse line range from string like "file.py:25-50" or "file.py:25" or "file.py#L25-L50"
    const lineMatch = filePath.match(/[:#]L?(\d+)(?:-L?(\d+))?$/);
    if (lineMatch) {
      startLine = startLine || parseInt(lineMatch[1], 10);
      endLine = endLine || (lineMatch[2] ? parseInt(lineMatch[2], 10) : startLine);
      filePath = filePath.substring(0, lineMatch.index);
    }
  } else if (sourceParam && typeof sourceParam === "object") {
    filePath = sourceParam.filePath || sourceParam.file_path || sourceParam.path || "";
    startLine = startLine || sourceParam.startLine || sourceParam.start_line;
    endLine = endLine || sourceParam.endLine || sourceParam.end_line;
  }

  if (!filePath) return;

  modalTitle.textContent = filePath;
  if (langBadge) langBadge.style.display = "none";
  if (linesBadge) linesBadge.style.display = "none";

  codeView.innerHTML = `
    <div style="padding:24px; text-align:center; color:var(--text-muted); display:flex; align-items:center; justify-content:center; gap:8px;">
      <span class="spinner"></span> Loading source content for <code>${escapeHtml(filePath)}</code>...
    </div>
  `;
  modal.classList.add("active");

  try {
    const data = await fetchSourceCode(filePath, state.selectedRepository);
    const content = data.content || "";
    const lines = content.split("\n");

    if (langBadge && data.language) {
      langBadge.textContent = data.language;
      langBadge.style.display = "inline-block";
    }
    if (linesBadge && data.line_count) {
      linesBadge.textContent = `${data.line_count} lines`;
      linesBadge.style.display = "inline-block";
    }

    const effectiveStart = startLine || data.start_line;
    const effectiveEnd = endLine || data.end_line || effectiveStart;

    const codeHtml = lines.map((lineText, idx) => {
      const lineNum = idx + 1;
      const isHighlighted = effectiveStart && effectiveEnd && lineNum >= effectiveStart && lineNum <= effectiveEnd;
      const hlClass = isHighlighted ? "highlight" : "";
      return `
        <div class="code-line ${hlClass}" id="code-line-${lineNum}">
          <span class="line-num">${lineNum}</span>
          <span class="line-text">${escapeHtml(lineText)}</span>
        </div>
      `;
    }).join("");

    codeView.innerHTML = `<div class="code-view">${codeHtml}</div>`;

    if (effectiveStart) {
      setTimeout(() => {
        const targetEl = document.getElementById(`code-line-${effectiveStart}`);
        if (targetEl) {
          targetEl.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }, 120);
    }
  } catch (err) {
    codeView.innerHTML = `
      <div style="padding:24px; background:rgba(244,63,94,0.06); border:1px solid rgba(244,63,94,0.25); border-radius:8px; margin:10px 0;">
        <div style="font-weight:700; color:var(--accent-rose); font-size:14px; margin-bottom:6px;">Unable to load source</div>
        <div style="color:var(--text-secondary); font-size:13px; line-height:1.5;">
          The referenced file <code>${escapeHtml(filePath)}</code> could not be located in repository <strong>${escapeHtml(state.selectedRepository || 'default')}</strong>. The source index may be outdated or the reference path may no longer exist.
        </div>
      </div>
    `;
  }
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(text) {
  if (!text) return "";
  return String(text).replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
