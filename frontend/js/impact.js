/**
 * Impact Analysis & API Flow UI Handlers.
 */

import { analyzeApiFlow, analyzeImpact } from "./api.js";
import { updateGraphData } from "./graph.js";
import { state } from "./state.js";

export function initImpactView() {
  const impactBtn = document.getElementById("btn-run-impact");
  const apiFlowBtn = document.getElementById("btn-run-apiflow");

  if (impactBtn) {
    impactBtn.addEventListener("click", () => handleImpactSubmit());
  }

  if (apiFlowBtn) {
    apiFlowBtn.addEventListener("click", () => handleApiFlowSubmit());
  }
}

export async function handleImpactSubmit() {
  const symbolInput = document.getElementById("impact-symbol-input");
  const hopsInput = document.getElementById("impact-hops-input");
  const impactBtn = document.getElementById("btn-run-impact");
  const resultsContainer = document.getElementById("impact-results");

  const symbol = symbolInput ? symbolInput.value.trim() : "";
  const hops = hopsInput ? parseInt(hopsInput.value, 10) : 2;

  if (!symbol) return;

  if (impactBtn) {
    impactBtn.disabled = true;
    impactBtn.innerHTML = `<span class="spinner"></span> Analyzing Impact...`;
  }

  try {
    const payload = {
      target_symbol: symbol,
      repository_id: state.selectedRepository || "default",
      max_hops: hops,
    };

    const response = await analyzeImpact(payload);
    state.setImpactResult(response);

    if (resultsContainer) {
      const summary = response.summary || {};
      const targetName = response.target ? (response.target.qualified_name || response.target.name) : symbol;
      const totalDependents = (summary.direct_dependents_count || 0) + (summary.transitive_dependents_count || 0);
      const fileCount = summary.affected_files_count || (response.affected_files || []).length;

      const indicatorTag = totalDependents > 5 ? "tag-rose" : totalDependents > 0 ? "tag-amber" : "tag-emerald";
      const indicatorText = `${totalDependents} Dependents (${fileCount} Files)`;

      resultsContainer.innerHTML = `
        <div class="card">
          <div class="card-title">
            <span>Impact Target: <code>${targetName}</code></span>
            <span class="tag ${indicatorTag}">${indicatorText}</span>
          </div>
          <div style="font-size:13px; color:var(--text-secondary)">
            ${response.explanation || 'Code impact graph compiled.'}
          </div>
          <table class="kv-table">
            <tr>
              <td class="kv-key">Direct Upstream Dependents</td>
              <td class="kv-val">${summary.direct_dependents_count || (response.direct_dependents || []).length} symbols</td>
            </tr>
            <tr>
              <td class="kv-key">Transitive Dependents</td>
              <td class="kv-val">${summary.transitive_dependents_count || (response.transitive_dependents || []).length} symbols</td>
            </tr>
            <tr>
              <td class="kv-key">Downstream Dependencies</td>
              <td class="kv-val">${summary.direct_dependencies_count || (response.direct_dependencies || []).length} symbols</td>
            </tr>
            <tr>
              <td class="kv-key">Affected Files</td>
              <td class="kv-val">${(response.affected_files || []).join(", ") || "None"}</td>
            </tr>
            <tr>
              <td class="kv-key">Max Traversal Depth</td>
              <td class="kv-val">${summary.max_hops_used || hops} hops</td>
            </tr>
          </table>
        </div>
      `;
    }

    // Visualize impact graph
    const nodes = [];
    const rels = [];

    // Target node
    nodes.push({
      id: "target_" + response.target_symbol,
      name: response.target_symbol,
      label: "Class",
      symbol_type: "TARGET",
    });

    (response.direct_dependencies || []).forEach((dep, idx) => {
      nodes.push({ id: "dep_" + idx, name: dep, label: "Function" });
      rels.push({ id: "rel_dep_" + idx, source: "target_" + response.target_symbol, target: "dep_" + idx, type: "DEPENDS_ON" });
    });

    (response.direct_dependents || []).forEach((dep, idx) => {
      nodes.push({ id: "dept_" + idx, name: dep, label: "Function" });
      rels.push({ id: "rel_dept_" + idx, source: "dept_" + idx, target: "target_" + response.target_symbol, type: "CALLS" });
    });

    updateGraphData({ nodes, relationships: rels });

  } catch (err) {
    if (resultsContainer) {
      resultsContainer.innerHTML = `<span style="color:var(--accent-rose)">Impact Analysis Failed: ${err.message}</span>`;
    }
  } finally {
    if (impactBtn) {
      impactBtn.disabled = false;
      impactBtn.innerHTML = `Run Impact Analysis`;
    }
  }
}

export async function handleApiFlowSubmit() {
  const flowInput = document.getElementById("apiflow-input");
  const apiFlowBtn = document.getElementById("btn-run-apiflow");
  const flowResults = document.getElementById("apiflow-results");

  const identifier = flowInput ? flowInput.value.trim() : "";
  if (!identifier) return;

  if (apiFlowBtn) {
    apiFlowBtn.disabled = true;
    apiFlowBtn.innerHTML = `<span class="spinner"></span> Tracing API Flow...`;
  }

  try {
    const payload = {
      path_or_symbol: identifier,
      repository_id: state.selectedRepository || null,
      max_hops: 3,
    };

    const response = await analyzeApiFlow(payload);
    state.setApiFlowResult(response);

    if (flowResults) {
      if (response.paths_found === 0) {
        flowResults.innerHTML = `<div style="color:var(--text-muted); padding:10px;">No connected API flow paths found for "${identifier}".</div>`;
      } else {
        const pathItems = response.paths.map((p, idx) => {
          const pathNodes = p.path_nodes || [];
          const pathRels = p.path_relationships || [];
          const stepChain = pathNodes.map(n => typeof n === 'object' ? (n.name || n.file_path) : n).join(" → ");
          return `
            <div class="tree-node">
              <div>
                <strong>Flow #${idx + 1}:</strong> ${stepChain}
                <div style="font-size:11px; color:var(--text-muted); margin-top:2px;">
                  Rels: ${pathRels.join(" → ") || "MATCHES"}
                </div>
              </div>
              <span class="tag tag-blue">API Flow</span>
            </div>
          `;
        }).join("");

        flowResults.innerHTML = `
          <div class="card">
            <div class="card-title">
              <span>API Flow Traces for <code>${response.query_term}</code></span>
              <span class="tag tag-purple">${response.paths_found} Paths Found</span>
            </div>
            ${pathItems}
          </div>
        `;
      }
    }
  } catch (err) {
    if (flowResults) {
      flowResults.innerHTML = `<span style="color:var(--accent-rose)">API Flow Analysis Failed: ${err.message}</span>`;
    }
  } finally {
    if (apiFlowBtn) {
      apiFlowBtn.disabled = false;
      apiFlowBtn.innerHTML = `Trace API Flow`;
    }
  }
}
