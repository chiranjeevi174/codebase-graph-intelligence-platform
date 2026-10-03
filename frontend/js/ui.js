/**
 * Main UI Controller - Coordinates layout, tabs, modals, sidebar, and repository controls.
 */

import { fetchGraphData, fetchHealthStatus, fetchRepositories, fetchSourceCode, ingestRepository } from "./api.js";
import { initDiffView } from "./diff.js";
import { highlightPath, initGraphVisualization, resetGraphZoom, updateGraphData, zoomIn, zoomOut } from "./graph.js";
import { initImpactView } from "./impact.js";
import { initPRView } from "./pr.js";
import { initQueryView } from "./query.js";
import { state } from "./state.js";

export function initUI() {
  initTabs();
  initRepositoryControls();
  initModalListeners();
  initGraphControls();

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
      ingestBtn.innerHTML = `<span class="spinner"></span> Ingesting...`;

      try {
        const payload = {
          repository_path: repoPath || null,
          repository_url: repoUrl || null,
          branch: branch || null,
          force: force,
        };
        const result = await ingestRepository(payload);
        alert(`Ingestion Successful!\nRepository ID: ${result.repository_id}\nFiles Processed: ${result.files_processed}\nSymbols: ${result.symbols_extracted}`);
        refreshRepositories();
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

  if (btnZoomIn) btnZoomIn.addEventListener("click", () => zoomIn());
  if (btnZoomOut) btnZoomOut.addEventListener("click", () => zoomOut());
  if (btnReset) btnReset.addEventListener("click", () => resetGraphZoom());
}

function initModalListeners() {
  const modal = document.getElementById("source-modal");
  const closeBtn = document.getElementById("btn-close-modal");

  if (closeBtn && modal) {
    closeBtn.addEventListener("click", () => {
      modal.classList.remove("active");
    });
  }
}

async function refreshHealth() {
  const badge = document.getElementById("health-badge");
  try {
    const health = await fetchHealthStatus();
    state.setHealth(health);

    if (badge) {
      badge.className = "status-badge";
      badge.innerHTML = `<span class="status-dot"></span> System Healthy (${health.llm_provider} / ${health.embedding_model})`;
    }
  } catch (err) {
    if (badge) {
      badge.className = "status-badge warning";
      badge.innerHTML = `<span class="status-dot"></span> System Offline (${err.message})`;
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
      if (repos.length === 0) {
        listContainer.innerHTML = `<div style="color:var(--text-muted); font-size:12px;">Default sample repositories loaded. Ingest new repos above.</div>`;
      } else {
        listContainer.innerHTML = repos.map((r) => `
          <div class="tree-node">
            <div>
              <strong>${r.name}</strong>
              <div style="font-size:11px; color:var(--text-muted)">Files: ${r.files_processed} | Symbols: ${r.symbols_extracted}</div>
            </div>
            <span class="tag tag-emerald">Indexed</span>
          </div>
        `).join("");
      }
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

function renderRightPanelNodeDetails(node) {
  const panel = document.getElementById("node-details-container");
  if (!panel) return;

  if (!node) {
    panel.innerHTML = `<div style="color:var(--text-muted); font-size:12px;">Click any graph node to inspect symbol attributes and code location.</div>`;
    return;
  }

  panel.innerHTML = `
    <div class="card">
      <div class="card-title">
        <span>${node.name || 'Selected Node'}</span>
        <span class="tag tag-blue">${node.label || node.symbolType || 'Node'}</span>
      </div>
      <table class="kv-table">
        <tr>
          <td class="kv-key">Qualified Name</td>
          <td class="kv-val">${node.qualifiedName || node.name || 'N/A'}</td>
        </tr>
        <tr>
          <td class="kv-key">File Path</td>
          <td class="kv-val">
            <a href="#" id="link-open-file" style="color:var(--accent-blue); text-decoration:none;">${node.filePath || 'N/A'}</a>
          </td>
        </tr>
        <tr>
          <td class="kv-key">Line Range</td>
          <td class="kv-val">L${node.startLine || 1} - L${node.endLine || 1}</td>
        </tr>
        <tr>
          <td class="kv-key">Language</td>
          <td class="kv-val">${node.language || 'N/A'}</td>
        </tr>
      </table>
    </div>
  `;

  const link = document.getElementById("link-open-file");
  if (link && node.filePath) {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      openSourceModal(node.filePath, node.startLine, node.endLine);
    });
  }
}

async function openSourceModal(filePath, startLine = null, endLine = null) {
  const modal = document.getElementById("source-modal");
  const modalTitle = document.getElementById("modal-file-title");
  const codeView = document.getElementById("modal-code-content");

  if (!modal || !codeView) return;

  modalTitle.textContent = filePath;
  codeView.innerHTML = `<em style="color:var(--text-muted)">Loading source content for ${filePath}...</em>`;
  modal.classList.add("active");

  try {
    const data = await fetchSourceCode(filePath, state.selectedRepository);
    const lines = (data.content || "").split("\n");

    const codeHtml = lines.map((lineText, idx) => {
      const lineNum = idx + 1;
      const isHighlighted = startLine && endLine && lineNum >= startLine && lineNum <= endLine;
      const hlClass = isHighlighted ? "highlight" : "";
      return `
        <div class="code-line ${hlClass}">
          <span class="line-num">${lineNum}</span>
          <span class="line-text">${escapeHtml(lineText)}</span>
        </div>
      `;
    }).join("");

    codeView.innerHTML = `<div class="code-view">${codeHtml}</div>`;

    if (startLine) {
      setTimeout(() => {
        const highlightedEl = codeView.querySelector(".code-line.highlight");
        if (highlightedEl) highlightedEl.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 100);
    }
  } catch (err) {
    codeView.innerHTML = `<span style="color:var(--accent-rose)">Failed loading file content: ${err.message}</span>`;
  }
}

function escapeHtml(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
