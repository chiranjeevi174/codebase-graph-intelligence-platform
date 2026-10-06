/**
 * Impact Analysis & API Flow UI Handlers.
 * Implements variable hop depth (1, 2, 3, All), deterministic deduplicated counts, and scoped API flow traces.
 */

import { analyzeApiFlow, analyzeImpact } from "./api.js";
import { highlightPath, updateGraphData } from "./graph.js";
import { state } from "./state.js";

export function initImpactView() {
  const impactBtn = document.getElementById("btn-run-impact");
  const apiFlowBtn = document.getElementById("btn-run-apiflow");
  const symbolInput = document.getElementById("impact-symbol-input");
  const apiflowInput = document.getElementById("apiflow-input");

  if (impactBtn) {
    impactBtn.addEventListener("click", () => handleImpactSubmit());
  }

  if (symbolInput) {
    symbolInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleImpactSubmit();
      }
    });
  }

  if (apiFlowBtn) {
    apiFlowBtn.addEventListener("click", () => handleApiFlowSubmit());
  }

  if (apiflowInput) {
    apiflowInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleApiFlowSubmit();
      }
    });
  }
}

export async function handleImpactSubmit() {
  const symbolInput = document.getElementById("impact-symbol-input");
  const hopsInput = document.getElementById("impact-hops-input");
  const impactBtn = document.getElementById("btn-run-impact");
  const resultsContainer = document.getElementById("impact-results");

  const symbol = symbolInput ? symbolInput.value.trim() : "";
  const rawHops = hopsInput ? hopsInput.value : "2";
  const hops = rawHops === "all" ? "all" : parseInt(rawHops, 10);

  if (!symbol) return;

  if (impactBtn) {
    impactBtn.disabled = true;
    impactBtn.innerHTML = `<span class="spinner"></span> Analyzing Impact...`;
  }

  try {
    const payload = {
      symbol: symbol,
      repository_id: state.selectedRepository || null,
      max_hops: hops,
    };

    const response = await analyzeImpact(payload);
    state.setImpactResult(response);

    if (resultsContainer) {
      const summary = response.summary || {};
      const targetEntity = response.target || {};
      const targetName = targetEntity.qualified_name || targetEntity.name || symbol;
      const targetType = targetEntity.symbol_type || "Symbol";
      const totalDependents = (summary.direct_dependents_count || 0) + (summary.transitive_dependents_count || 0);
      const totalDependencies = (summary.direct_dependencies_count || 0) + (summary.transitive_dependencies_count || 0);
      const fileCount = summary.affected_files_count || (response.affected_files || []).length;
      const displayHops = summary.max_hops_used != null ? summary.max_hops_used : rawHops;

      const indicatorTag = totalDependents > 5 ? "tag-rose" : totalDependents > 0 ? "tag-amber" : "tag-emerald";
      const indicatorText = `${totalDependents} Dependents (${fileCount} Files)`;

      const directDepList = (response.direct_dependents || []).map((d) => `<code>${escapeHtml(d.name || d.qualified_name)}</code>`).join(", ") || "None";
      const transDepList = (response.transitive_dependents || []).map((d) => `<code>${escapeHtml(d.name || d.qualified_name)}</code>`).join(", ") || "None";
      const directDownList = (response.direct_dependencies || []).map((d) => `<code>${escapeHtml(d.name || d.qualified_name)}</code>`).join(", ") || "None";
      const filesList = (response.affected_files || []).map((f) => `<code>${escapeHtml(f)}</code>`).join(", ") || "None";

      resultsContainer.innerHTML = `
        <div class="card">
          <div class="card-title">
            <div class="title-with-badge">
              <span>Impact Target: <code>${escapeHtml(targetName)}</code></span>
              <span class="tag tag-blue">${escapeHtml(targetType)}</span>
            </div>
            <span class="tag ${indicatorTag}">${indicatorText}</span>
          </div>

          <div style="font-size:13px; color:var(--text-secondary); line-height:1.5;">
            ${escapeHtml(response.explanation || 'Code impact analysis and dependency propagation graph compiled.')}
          </div>

          <table class="kv-table">
            <tr>
              <td class="kv-key">Direct Upstream Dependents</td>
              <td class="kv-val">${summary.direct_dependents_count || 0} symbols — ${directDepList}</td>
            </tr>
            <tr>
              <td class="kv-key">Transitive Dependents</td>
              <td class="kv-val">${summary.transitive_dependents_count || 0} symbols — ${transDepList}</td>
            </tr>
            <tr>
              <td class="kv-key">Downstream Dependencies</td>
              <td class="kv-val">${summary.direct_dependencies_count || 0} symbols — ${directDownList}</td>
            </tr>
            <tr>
              <td class="kv-key">Affected Source Files</td>
              <td class="kv-val">${filesList}</td>
            </tr>
            <tr>
              <td class="kv-key">Traversal Scope</td>
              <td class="kv-val">${displayHops === 'all' || displayHops === 10 ? 'All Reachable Hops' : `${displayHops} Hops`}</td>
            </tr>
          </table>
        </div>
      `;
    }

    // Visualize impact graph on Cytoscape
    const nodes = [];
    const rels = [];
    const seenNodes = new Set();

    function addImpactNode(id, name, qn, label, symType, fpath, startL, endL) {
      if (!id || seenNodes.has(id)) return;
      seenNodes.add(id);
      nodes.push({
        id: String(id),
        name: name || qn || id,
        qualified_name: qn || name || "",
        label: label || "Symbol",
        symbol_type: symType || label || "Symbol",
        file_path: fpath || "",
        start_line: startL || 1,
        end_line: endL || 1,
      });
    }

    const targetId = "target_" + (response.target ? response.target.symbol_id : symbol);
    addImpactNode(
      targetId,
      response.target ? response.target.name : symbol,
      response.target ? response.target.qualified_name : symbol,
      response.target ? response.target.symbol_type : "Class",
      response.target ? response.target.symbol_type : "Class",
      response.target ? response.target.file_path : "",
    );

    (response.direct_dependents || []).forEach((dep, idx) => {
      const depId = "dept_" + (dep.symbol_id || idx);
      addImpactNode(depId, dep.name, dep.qualified_name, dep.symbol_type, dep.symbol_type, dep.file_path, dep.start_line, dep.end_line);
      rels.push({ id: `rel_dept_${idx}`, source: depId, target: targetId, type: dep.relationship_type || "CALLS" });
    });

    (response.transitive_dependents || []).forEach((dep, idx) => {
      const depId = "trans_dept_" + (dep.symbol_id || idx);
      addImpactNode(depId, dep.name, dep.qualified_name, dep.symbol_type, dep.symbol_type, dep.file_path, dep.start_line, dep.end_line);
      rels.push({ id: `rel_trans_dept_${idx}`, source: depId, target: targetId, type: dep.relationship_type || "TRANSITIVE_CALL" });
    });

    (response.direct_dependencies || []).forEach((dep, idx) => {
      const depId = "dep_" + (dep.symbol_id || idx);
      addImpactNode(depId, dep.name, dep.qualified_name, dep.symbol_type, dep.symbol_type, dep.file_path, dep.start_line, dep.end_line);
      rels.push({ id: `rel_dep_${idx}`, source: targetId, target: depId, type: dep.relationship_type || "DEPENDS_ON" });
    });

    if (nodes.length > 0) {
      updateGraphData({ nodes, relationships: rels });
    }

  } catch (err) {
    if (resultsContainer) {
      resultsContainer.innerHTML = `<span style="color:var(--accent-rose)">Impact Analysis Failed: ${escapeHtml(err.message)}</span>`;
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
      if (response.paths_found === 0 || !response.paths || response.paths.length === 0) {
        flowResults.innerHTML = `
          <div class="card">
            <div style="color:var(--text-muted); padding:6px 0;">
              No connected cross-language API flow paths found for <code>${escapeHtml(identifier)}</code> in repository <strong>${escapeHtml(state.selectedRepository || 'default')}</strong>.
            </div>
          </div>
        `;
      } else {
        const pathItems = response.paths.map((p, idx) => {
          const pathNodes = p.path_nodes || [];
          const pathRels = p.path_relationships || [];
          const stepChain = pathNodes.map(n => {
            if (typeof n === "object" && n !== null) {
              return escapeHtml(n.name || n.qualified_name || n.file_path || "Endpoint");
            }
            return escapeHtml(String(n));
          }).join(" <span style='color:var(--accent-cyan); font-weight:700;'>→</span> ");

          return `
            <div class="tree-node">
              <div style="overflow:hidden; text-overflow:ellipsis;">
                <div style="font-weight:600; font-size:12.5px; margin-bottom:3px;">
                  Flow #${idx + 1}: ${stepChain}
                </div>
                <div style="font-size:11px; color:var(--text-muted); font-family:var(--font-mono);">
                  Relationship Sequence: ${(pathRels.map(r => escapeHtml(r)).join(" → ")) || "CONNECTED"}
                </div>
              </div>
              <span class="tag tag-purple">API Trace</span>
            </div>
          `;
        }).join("");

        flowResults.innerHTML = `
          <div class="card">
            <div class="card-title">
              <div class="title-with-badge">
                <span>API Flow Traces for <code>${escapeHtml(response.query_term)}</code></span>
                <span class="tag tag-blue">${escapeHtml(state.selectedRepository || 'All Repos')}</span>
              </div>
              <span class="tag tag-purple">${response.paths_found} Unique ${response.paths_found === 1 ? 'Flow' : 'Flows'} Found</span>
            </div>
            <div style="display:flex; flex-direction:column; gap:6px;">
              ${pathItems}
            </div>
          </div>
        `;
      }
    }
  } catch (err) {
    if (flowResults) {
      flowResults.innerHTML = `<span style="color:var(--accent-rose)">API Flow Analysis Failed: ${escapeHtml(err.message)}</span>`;
    }
  } finally {
    if (apiFlowBtn) {
      apiFlowBtn.disabled = false;
      apiFlowBtn.innerHTML = `Trace API Flow`;
    }
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
