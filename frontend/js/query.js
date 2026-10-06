/**
 * Codebase Query UI Handler (Graph RAG Workflow).
 * Provides dynamic repository-specific suggestions and grounded evidence citation exploration.
 */

import { executeQuery } from "./api.js";
import { updateGraphData } from "./graph.js";
import { state } from "./state.js";

const REPOSITORY_SUGGESTIONS = {
  sample_repo: [
    { label: "User Auth & JWT Flow", prompt: "How does user authentication and JWT validation work across routes?" },
    { label: "Trace /api/orders", prompt: "Trace the /api/orders endpoint to the database and payment service." },
    { label: "UserService Dependents", prompt: "What components and handlers depend directly or indirectly on UserService?" },
    { label: "Payment Checkout Logic", prompt: "How is payment processing handled in PaymentService and OrderService?" },
    { label: "Architecture Summary", prompt: "Explain the high-level architecture, models, and service boundaries in sample_repo." },
  ],
  multi_language_repo: [
    { label: "Polyglot Architecture", prompt: "How do Python, TypeScript, Go, and Java components interoperate in this repository?" },
    { label: "Cross-Language API Contracts", prompt: "Trace API contracts and endpoints shared between the Go service and Python backend." },
    { label: "Go Inventory Handlers", prompt: "Which Go handlers handle inventory management and API client requests?" },
    { label: "Java Service Dependencies", prompt: "What backend services call the Java order processing or database layer?" },
    { label: "TypeScript Client Calls", prompt: "Where are the TypeScript API client calls defined and which endpoints do they hit?" },
  ],
  diff_repo: [
    { label: "Changed AST Symbols", prompt: "What AST symbols and methods were modified or added between HEAD~1 and HEAD?" },
    { label: "Structural Refactoring Impact", prompt: "What is the structural blast radius of recent changes in the repository?" },
    { label: "Modified API Contracts", prompt: "Were any API routes or model signatures changed in the latest commit?" },
    { label: "Compare Recent Commits", prompt: "Summarize code and signature evolution across recent commits." },
  ],
};

export function initQueryView() {
  const queryBtn = document.getElementById("btn-run-query");
  const queryInput = document.getElementById("query-input");

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

  // Render initial suggestions for current repo
  renderRepositorySuggestions(state.selectedRepository || "sample_repo");

  // Subscribe to repo changes to refresh suggestions dynamically
  state.subscribe((event, data) => {
    if (event === "repo_changed") {
      renderRepositorySuggestions(data);
    }
  });
}

/**
 * Render repository-specific question suggestions dynamically.
 */
export function renderRepositorySuggestions(repoId) {
  const container = document.getElementById("query-suggestions-list");
  if (!container) return;

  const suggestions = REPOSITORY_SUGGESTIONS[repoId] || [
    { label: "Core Architecture", prompt: `Explain the core architecture, classes, and entrypoints of ${repoId}.` },
    { label: "API Endpoints & Routes", prompt: `What API routes and HTTP handlers are defined in ${repoId}?` },
    { label: "Service Dependencies", prompt: `Trace key service dependencies and database operations in ${repoId}.` },
    { label: "Key Classes & Methods", prompt: `What are the primary classes and function workflows in ${repoId}?` },
  ];

  container.innerHTML = suggestions.map((s) => `
    <button type="button" class="prompt-chip" data-prompt="${escapeAttr(s.prompt)}" title="${escapeAttr(s.prompt)}">
      ${escapeHtml(s.label)}
    </button>
  `).join("");

  // Attach click listeners to new chips
  container.querySelectorAll(".prompt-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      const queryInput = document.getElementById("query-input");
      if (queryInput) {
        queryInput.value = chip.dataset.prompt || chip.innerText.trim();
        handleQuerySubmit();
      }
    });
  });
}

/**
 * Adapt backend GraphPath items into Cytoscape-compatible nodes and relationships.
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
        qualified_name: rawNode.qualified_name || rawNode.name || "",
        label: label,
        symbol_type: rawNode.symbol_type || label,
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

    const sourceId = addNode(sourceNode);
    const targetId = addNode(targetNode);

    if (Array.isArray(p.nodes)) {
      p.nodes.forEach((n) => addNode(n));
    }

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
        const errorText = response.validation_errors ? response.validation_errors.join("; ") : "Ungrounded claims detected";
        validationBadge.innerHTML = `<span class="status-dot"></span> Validation Warning: ${escapeHtml(errorText)}`;
      }
    }

    // Render Sources as Clickable Interactive Pills
    if (sourcesContainer) {
      sourcesContainer.innerHTML = "";
      if (response.sources && response.sources.length > 0) {
        response.sources.forEach((src) => {
          const pill = document.createElement("button");
          pill.type = "button";
          pill.className = "source-pill";
          pill.textContent = src;
          pill.title = `Click to inspect code at ${src}`;
          pill.addEventListener("click", () => {
            state.setSelectedSource(src);
          });
          sourcesContainer.appendChild(pill);
        });
      } else {
        sourcesContainer.innerHTML = `<span style="color:var(--text-muted); font-size:12px;">No direct sources cited in response</span>`;
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
            <div><strong>Query Intent:</strong> ${escapeHtml(trace.query_intent || 'N/A')}</div>
            <div><strong>Resolved Entities:</strong> ${escapeHtml((trace.resolved_entities || []).join(', ') || 'None')}</div>
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
    if (answerText) {
      answerText.innerHTML = `<span style="color:var(--accent-rose)">Error executing query: ${escapeHtml(err.message)}</span>`;
    }
  } finally {
    if (queryBtn) {
      queryBtn.disabled = false;
      queryBtn.innerHTML = `Send Question`;
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

function escapeAttr(text) {
  if (!text) return "";
  return String(text).replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
