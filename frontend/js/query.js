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
    if (response.graph_paths && response.graph_paths.length > 0) {
      const subgraphNodes = [];
      const subgraphRels = [];
      const seenNodes = new Set();

      response.graph_paths.forEach((p, pIdx) => {
        p.nodes.forEach((n) => {
          if (!seenNodes.has(n.symbol_id)) {
            seenNodes.add(n.symbol_id);
            subgraphNodes.push({
              id: n.symbol_id,
              name: n.name,
              qualified_name: n.qualified_name,
              label: n.symbol_type || "Symbol",
              file_path: n.file_path,
              start_line: n.start_line,
              end_line: n.end_line,
            });
          }
        });
        p.relationships.forEach((r, rIdx) => {
          subgraphRels.push({
            id: `sub_${pIdx}_${rIdx}`,
            source: r.source_id,
            target: r.target_id,
            type: r.relationship_type,
          });
        });
      });

      updateGraphData({
        nodes: subgraphNodes,
        relationships: subgraphRels,
      });
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
