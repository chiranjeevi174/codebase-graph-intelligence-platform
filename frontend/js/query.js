/**
 * Codebase Query UI Handler (Graph RAG Workflow).
 */

import { executeQuery } from "./api.js";
import { updateGraphData } from "./graph.js";
import { state } from "./state.js";

export function initQueryView() {
  const queryBtn = document.getElementById("btn-run-query");
  const queryInput = document.getElementById("query-input");
  const suggestions = document.querySelectorAll(".prompt-chip");

  if (queryBtn) {
    queryBtn.addEventListener("click", () => handleQuerySubmit());
  }

  if (queryInput) {
    queryInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleQuerySubmit();
      }
    });
  }

  suggestions.forEach((chip) => {
    chip.addEventListener("click", () => {
      if (queryInput) {
        queryInput.value = chip.dataset.prompt || chip.innerText.trim();
        handleQuerySubmit();
      }
    });
  });
}

/**
 * Adapt backend GraphPath items into Cytoscape-compatible nodes and relationships.
 * Safely handles current GraphPath schema:
 *   { source_node, target_node, relationships, hop_count, path_sequence }
 *
 * @param {Array} graphPaths
 * @returns {{ nodes: Array, relationships: Array }}
 */
function adaptGraphPaths(graphPaths) {
  const nodes = [];
  const relationships = [];
  const seenNodes = new Set();

  if (!Array.isArray(graphPaths)) {
    return { nodes, relationships };
  }

  function addNode(rawNode) {
    if (!rawNode || typeof rawNode !== "object") return null;
    const id = rawNode.id != null ? String(rawNode.id) : (rawNode.symbol_id != null ? String(rawNode.symbol_id) : null);
    if (!id) return null;

    if (!seenNodes.has(id)) {
      seenNodes.add(id);
      const label = (Array.isArray(rawNode.labels) && rawNode.labels.length > 0)
        ? rawNode.labels[0]
        : (rawNode.label || rawNode.symbol_type || "Symbol");

      nodes.push({
        id: id,
        name: rawNode.name || rawNode.qualified_name || id,
        qualified_name: rawNode.qualified_name || "",
        label: label,
        file_path: rawNode.file_path || "",
        start_line: typeof rawNode.start_line === "number" ? rawNode.start_line : 1,
        end_line: typeof rawNode.end_line === "number" ? rawNode.end_line : 1,
      });
    }
    return id;
  }

  graphPaths.forEach((p, pIdx) => {
    if (!p || typeof p !== "object") return;

    const sourceNode = p.source_node;
    const targetNode = p.target_node;
    const rels = Array.isArray(p.relationships) ? p.relationships : [];
    const hopCount = typeof p.hop_count === "number" ? p.hop_count : 1;
    const pathSequence = Array.isArray(p.path_sequence) ? p.path_sequence : [];

    const sourceId = addNode(sourceNode);
    const targetId = addNode(targetNode);

    // Backward-compatibility: if legacy p.nodes exists, safely index them
    if (Array.isArray(p.nodes)) {
      p.nodes.forEach((n) => addNode(n));
    }

    // Single-hop path: create direct edge between endpoints
    if (hopCount === 1 && sourceId && targetId) {
      let relType = "RELATED";
      if (rels.length > 0) {
        if (typeof rels[0] === "string" && rels[0].trim()) {
          relType = rels[0].trim();
        } else if (rels[0] && typeof rels[0] === "object" && rels[0].relationship_type) {
          relType = String(rels[0].relationship_type).trim();
        }
      }

      relationships.push({
        id: `path_edge_${pIdx}_${sourceId}_${targetId}`,
        source: sourceId,
        target: targetId,
        type: relType,
      });
    } else if (Array.isArray(p.relationships)) {
      // Legacy edge support if relationships contains object descriptors
      p.relationships.forEach((r, rIdx) => {
        if (r && typeof r === "object" && r.source_id && r.target_id) {
          relationships.push({
            id: `sub_${pIdx}_${rIdx}`,
            source: String(r.source_id),
            target: String(r.target_id),
            type: r.relationship_type || "RELATED",
          });
        }
      });
    }
  });

  return { nodes, relationships };
}

export async function handleQuerySubmit() {
  const queryInput = document.getElementById("query-input");
  const queryBtn = document.getElementById("btn-run-query");
  const answerContainer = document.getElementById("answer-container");
  const answerText = document.getElementById("answer-text");
  const validationBadge = document.getElementById("validation-badge");
  const sourcesContainer = document.getElementById("sources-list");
  const debugTraceContainer = document.getElementById("debug-trace-container");

  const question = queryInput ? queryInput.value.trim() : "";
  if (!question) return;

  // Show loading state
  if (queryBtn) {
    queryBtn.disabled = true;
    queryBtn.innerHTML = `<span class="spinner"></span> Reasoning over graph...`;
  }
  if (answerText) {
    answerText.innerHTML = `<em style="color:var(--text-muted)">Running Graph RAG multi-hop reasoning & retrieval...</em>`;
  }
  if (answerContainer) answerContainer.style.display = "flex";

  try {
    const payload = {
      question: question,
      repository_id: state.selectedRepository || null,
      graph_top_k: 10,
      semantic_top_k: 10,
      final_top_k: 10,
      max_hops: 2,
      debug: true,
    };

    const response = await executeQuery(payload);
    state.setQueryResponse(response);

    // Display Grounded Answer
    if (answerText) {
      answerText.textContent = response.answer || "No answer generated.";
    }

    // Display Groundedness Validation Status
    if (validationBadge) {
      if (response.validation_status) {
        validationBadge.className = "status-badge";
        validationBadge.innerHTML = `<span class="status-dot"></span> Grounded Evidence Validated`;
      } else {
        validationBadge.className = "status-badge warning";
        const errorText = response.validation_errors ? response.validation_errors.join("; ") : "Ungrounded claims";
        validationBadge.innerHTML = `<span class="status-dot"></span> Validation Warning: ${errorText}`;
      }
    }

    // Render Sources as Clickable Pills
    if (sourcesContainer) {
      sourcesContainer.innerHTML = "";
      if (response.sources && response.sources.length > 0) {
        response.sources.forEach((src) => {
          const pill = document.createElement("button");
          pill.className = "source-pill";
          pill.textContent = src;
          pill.title = `View source code for ${src}`;
          pill.addEventListener("click", () => {
            state.setSelectedSource(src);
          });
          sourcesContainer.appendChild(pill);
        });
      } else {
        sourcesContainer.innerHTML = `<span style="color:var(--text-muted); font-size:12px;">No direct sources cited</span>`;
      }
    }

    // Render Subgraph visualization if present
    if (Array.isArray(response.graph_paths) && response.graph_paths.length > 0) {
      const graphData = adaptGraphPaths(response.graph_paths);
      if (graphData.nodes.length > 0) {
        updateGraphData(graphData);
      }
    }

    // Debug Trace Panel
    if (debugTraceContainer) {
      if (response.retrieval_trace) {
        const trace = response.retrieval_trace;
        debugTraceContainer.innerHTML = `
          <div style="font-size:12px; font-family:var(--font-mono); color:var(--text-secondary); display:flex; flex-direction:column; gap:6px;">
            <div><strong>Query Intent:</strong> ${trace.query_intent || 'N/A'}</div>
            <div><strong>Resolved Entities:</strong> ${(trace.resolved_entities || []).join(', ') || 'None'}</div>
            <div><strong>Graph Matches:</strong> ${trace.graph_results_count || 0}</div>
            <div><strong>Semantic Vector Matches:</strong> ${trace.semantic_results_count || 0}</div>
            <div><strong>Fused RRF Results:</strong> ${trace.fused_results_count || 0}</div>
            <div><strong>Subgraph Paths:</strong> ${trace.subgraph_paths_count || 0}</div>
          </div>
        `;
      }
    }
  } catch (err) {
    console.error("GRAPH RAG QUERY ERROR:", err);
    console.error("GRAPH RAG QUERY ERROR MESSAGE:", err?.message);
    console.error("GRAPH RAG QUERY ERROR STACK:", err?.stack);

    if (answerText) {
      answerText.innerHTML = `<span style="color:var(--accent-rose)">Error executing query: ${err.message}</span>`;
    }
  } finally {
    if (queryBtn) {
      queryBtn.disabled = false;
      queryBtn.innerHTML = `Send Question`;
    }
  }
}
