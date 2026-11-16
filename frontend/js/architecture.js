/**
 * Architecture Intelligence & Visualization UI Handler.
 * Discovers modules, architectural layers, entry points, and renders Cytoscape graphs.
 */

import { analyzeArchitecture } from "./api.js";
import { updateGraphData } from "./graph.js";
import { state } from "./state.js";

export function initArchitectureView() {
  const runBtn = document.getElementById("btn-run-architecture");
  const levelSelect = document.getElementById("architecture-level-select");

  if (runBtn) {
    runBtn.addEventListener("click", () => handleArchitectureSubmit());
  }

  if (levelSelect) {
    levelSelect.addEventListener("change", () => handleArchitectureSubmit());
  }
}

export async function handleArchitectureSubmit() {
  const runBtn = document.getElementById("btn-run-architecture");
  const levelSelect = document.getElementById("architecture-level-select");
  const resultsContainer = document.getElementById("architecture-results");

  const repoId = state.selectedRepository || "sample_repo";
  const level = levelSelect ? levelSelect.value : "overview";

  if (runBtn) {
    runBtn.disabled = true;
    runBtn.innerHTML = `<span class="spinner"></span> Discovering Architecture...`;
  }

  try {
    const payload = {
      repository_id: repoId,
      level: level,
    };

    const response = await analyzeArchitecture(payload);
    state.setArchitectureResult(response);

    // Update Cytoscape Graph Canvas with architectural graph
    if (response.nodes && response.nodes.length > 0) {
      const cyGraphPayload = {
        repository_id: repoId,
        nodes: response.nodes.map((n) => ({
          id: n.id,
          name: n.name,
          label: n.label,
          file_path: n.path,
          layer: n.layer,
          qualified_name: n.description,
          start_line: 1,
          end_line: 1,
        })),
        relationships: (response.edges || []).map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          type: e.type,
        })),
        node_distribution: {},
        relationship_distribution: {},
        metadata: {
          total_nodes: response.nodes.length,
          total_relationships: (response.edges || []).length,
        },
      };
      updateGraphData(cyGraphPayload);
    }

    if (resultsContainer) {
      renderArchitectureResults(response, resultsContainer);
    }
  } catch (err) {
    if (resultsContainer) {
      resultsContainer.innerHTML = `
        <div class="card error-card">
          <div class="card-title" style="color:var(--accent-rose)">Architecture Discovery Failed</div>
          <p style="color:var(--text-secondary); font-size:13px; margin-top:6px;">${escapeHtml(err.message)}</p>
        </div>
      `;
    }
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = `<span>Discover Architecture</span>`;
    }
  }
}

function renderArchitectureResults(data, container) {
  const summary = data.summary || {};
  const layers = data.layers || [];
  const entryPoints = data.entry_points || [];
  const nodes = data.nodes || [];
  const edges = data.edges || [];

  const entryListHtml =
    entryPoints.length > 0
      ? entryPoints
          .map(
            (ep) => `
        <div class="entry-point-pill" data-node-id="${escapeAttr(ep.id)}" title="${escapeAttr(ep.description || ep.name)}">
          <span class="ep-icon">🚀</span>
          <span class="ep-name">${escapeHtml(ep.name)}</span>
          <span class="tag tag-blue">${escapeHtml(ep.layer || 'Entry')}</span>
        </div>
      `
          )
          .join("")
      : `<span style="color:var(--text-muted); font-size:12px;">No standalone entry point detected.</span>`;

  const layersHtml = layers
    .map(
      (layer) => `
    <div class="card layer-card">
      <div class="card-title">
        <div class="layer-title-group">
          <span class="layer-indicator-dot"></span>
          <strong style="color:var(--text-primary); font-size:13.5px;">${escapeHtml(layer.name)}</strong>
        </div>
        <span class="tag tag-cyan">${layer.components.length} components</span>
      </div>
      <div style="font-size:12.5px; color:var(--text-secondary); margin:6px 0 10px 0; line-height:1.45;">
        ${escapeHtml(layer.description)}
      </div>
      <div class="component-chips-container">
        ${layer.components
          .map(
            (c) => `
          <button type="button" class="component-chip" data-component-name="${escapeAttr(c)}" title="Inspect ${escapeAttr(c)}">
            📄 ${escapeHtml(c)}
          </button>
        `
          )
          .join("")}
      </div>
    </div>
  `
    )
    .join("");

  container.innerHTML = `
    <!-- Top Metrics Overview Bar -->
    <div class="stat-grid" style="margin-bottom:14px;">
      <div class="stat-box">
        <span class="stat-label">Packages</span>
        <span class="stat-value" style="color:var(--accent-blue)">${summary.total_packages || 0}</span>
      </div>
      <div class="stat-box">
        <span class="stat-label">Files</span>
        <span class="stat-value" style="color:var(--accent-cyan)">${summary.total_files || 0}</span>
      </div>
      <div class="stat-box">
        <span class="stat-label">Classes</span>
        <span class="stat-value" style="color:var(--accent-purple)">${summary.total_classes || 0}</span>
      </div>
      <div class="stat-box">
        <span class="stat-label">Functions</span>
        <span class="stat-value" style="color:var(--accent-emerald)">${summary.total_functions || 0}</span>
      </div>
      <div class="stat-box">
        <span class="stat-label">Connections</span>
        <span class="stat-value" style="color:var(--accent-amber)">${edges.length}</span>
      </div>
    </div>

    <!-- Entry Points & Key Components Card -->
    <div class="card" style="margin-bottom:14px;">
      <div class="card-title">
        <span>Execution Entry Points</span>
        <span class="tag tag-emerald">Grounded</span>
      </div>
      <div class="entry-points-wrap" style="display:flex; flex-wrap:wrap; gap:8px; margin-top:8px;">
        ${entryListHtml}
      </div>
    </div>

    <!-- Grounded Architectural Explanation Card -->
    <div class="card" style="margin-bottom:14px;">
      <div class="card-title">
        <span>Architecture Intelligence Report</span>
        <span class="tag tag-purple">AI Grounded</span>
      </div>
      <div class="markdown-body" style="font-size:13px; line-height:1.6; color:var(--text-secondary); margin-top:10px;">
        ${renderMarkdown(data.explanation || 'Architecture discovery compiled.')}
      </div>
    </div>

    <!-- Architectural Layers Card Container -->
    <div class="card">
      <div class="card-title">
        <span>Discovered Architectural Layers</span>
        <span class="tag tag-blue">${layers.length} Layers</span>
      </div>
      <div class="layers-list-container" style="display:flex; flex-direction:column; gap:10px; margin-top:12px;">
        ${layersHtml}
      </div>
    </div>
  `;

  // Attach click listeners to entry points to select in Cytoscape
  container.querySelectorAll(".entry-point-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const nodeId = pill.dataset.nodeId;
      const targetNode = nodes.find((n) => n.id === nodeId);
      if (targetNode) {
        state.setSelectedNode({
          id: targetNode.id,
          name: targetNode.name,
          label: targetNode.label,
          filePath: targetNode.path,
          layer: targetNode.layer,
          qualifiedName: targetNode.description,
          startLine: 1,
          endLine: 1,
        });
      }
    });
  });

  // Attach click listeners to component chips to select node and open inspector
  container.querySelectorAll(".component-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const cName = chip.dataset.componentName;
      const targetNode = nodes.find((n) => n.name === cName || n.path.endsWith(cName));
      if (targetNode) {
        state.setSelectedNode({
          id: targetNode.id,
          name: targetNode.name,
          label: targetNode.label,
          filePath: targetNode.path,
          layer: targetNode.layer,
          qualifiedName: targetNode.description,
          startLine: 1,
          endLine: 1,
        });
      }
    });
  });
}

function renderMarkdown(text) {
  if (!text) return "";
  let out = escapeHtml(text);
  // Bold
  out = out.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Headings
  out = out.replace(/^#### (.*?)$/gm, "<h4 style='color:var(--text-primary); font-size:13px; margin:12px 0 4px;'>$1</h4>");
  out = out.replace(/^### (.*?)$/gm, "<h3 style='color:var(--text-primary); font-size:14px; margin:14px 0 6px;'>$1</h3>");
  out = out.replace(/^## (.*?)$/gm, "<h2 style='color:var(--text-primary); font-size:15px; margin:16px 0 8px;'>$1</h2>");
  // Inline code
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  // Bullet lists
  out = out.replace(/^- (.*?)$/gm, "<li style='margin-left:18px;'>$1</li>");
  // Paragraphs
  out = out.replace(/\n\n/g, "<br><br>");
  return out;
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
