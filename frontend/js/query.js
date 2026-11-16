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
    } else if (event === "query_response_updated") {
      const resultsContainer = document.getElementById("query-results") || document.getElementById("answer-container");
      if (resultsContainer && data && resultsContainer.innerHTML.includes("Submit a question above")) {
        renderQueryResponse(data, resultsContainer);
      }
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

/**
 * Render complete structured Grounded Answer card into target container.
 */
export function renderQueryResponse(response, container) {
  if (!container || !response) return;

  const answer = response.answer && response.answer.trim()
    ? renderMarkdown(response.answer)
    : `<em style="color:var(--text-muted)">No answer could be generated from the available codebase context.</em>`;

  const confPercent = Math.round((typeof response.confidence === "number" ? response.confidence : 0.8) * 100);
  const confTag = `<span class="tag tag-purple" data-tooltip-title="Answer Confidence" data-tooltip-body="Calculated based on AST evidence verification and reciprocal rank fusion">Confidence: ${confPercent}%</span>`;

  let validationBadgeHtml = "";
  if (response.validation_status) {
    validationBadgeHtml = `
      <span id="validation-badge" class="status-badge" data-tooltip-title="Grounded Evidence Validated" data-tooltip-body="All cited file paths and symbols verified against indexed codebase context">
        <span class="status-dot"></span> Grounded Evidence Validated
      </span>
    `;
  } else {
    const errors = Array.isArray(response.validation_errors) && response.validation_errors.length > 0
      ? response.validation_errors
      : ["Potentially unverified claims or citations detected"];
    const summaryText = errors.length === 1 ? errors[0] : `${errors.length} ungrounded citation(s): ${errors.join("; ")}`;
    validationBadgeHtml = `
      <span id="validation-badge" class="status-badge warning" data-tooltip-title="Grounding Notice" data-tooltip-body="${escapeAttr(errors.join("\n"))}">
        <span class="status-dot"></span> Grounding Notice: ${escapeHtml(summaryText)}
      </span>
    `;
  }

  const sources = Array.isArray(response.sources) ? response.sources : [];
  let sourcesSectionHtml = "";
  if (sources.length > 0) {
    const pills = sources
      .map(
        (src) => `
      <button type="button" class="source-pill" data-source="${escapeAttr(src)}" title="Click to inspect code at ${escapeAttr(src)}">
        📄 ${escapeHtml(src)}
      </button>
    `
      )
      .join("");

    sourcesSectionHtml = `
      <div class="sources-section">
        <div class="sources-header">VERIFIED CODEBASE CITATIONS (${sources.length})</div>
        <div id="sources-list" class="sources-list">
          ${pills}
        </div>
      </div>
    `;
  } else {
    sourcesSectionHtml = `
      <div class="sources-section">
        <div class="sources-header">VERIFIED CODEBASE CITATIONS</div>
        <div id="sources-list" class="sources-list">
          <span style="color:var(--text-muted); font-size:12px;">No direct file citations returned for this query.</span>
        </div>
      </div>
    `;
  }

  const debugTrace = response.debug_info || response.retrieval_trace;
  let debugTraceHtml = "";
  if (debugTrace) {
    const resolvedEntities = Array.isArray(debugTrace.resolved_entities)
      ? debugTrace.resolved_entities.join(", ")
      : "None";
    const graphCount = debugTrace.graph_results_count || 0;
    const semanticCount = debugTrace.semantic_results_count || 0;
    const fusedCount = Array.isArray(debugTrace.fused_results)
      ? debugTrace.fused_results.length
      : debugTrace.fused_results_count || 0;
    const pathCount =
      debugTrace.subgraph_stats && debugTrace.subgraph_stats.nodes != null
        ? `${debugTrace.subgraph_stats.nodes} nodes, ${debugTrace.subgraph_stats.edges || 0} edges`
        : Array.isArray(response.graph_paths)
        ? `${response.graph_paths.length} paths`
        : "0 paths";

    debugTraceHtml = `
      <details style="margin-top:8px; border-top:1px solid var(--border-color); padding-top:8px;">
        <summary style="font-size:11.5px; font-weight:600; color:var(--text-muted); cursor:pointer; user-select:none;">
          RETRIEVAL & REASONING TRACE
        </summary>
        <div id="debug-trace-container" style="font-size:12px; font-family:var(--font-mono); color:var(--text-secondary); display:flex; flex-direction:column; gap:6px; margin-top:8px; padding:10px; background:var(--bg-elevated); border-radius:var(--radius-md);">
          <div><strong>Query Intent:</strong> ${escapeHtml(debugTrace.query_intent || response.intent || "N/A")}</div>
          <div><strong>Resolved Entities:</strong> ${escapeHtml(resolvedEntities || "None")}</div>
          <div><strong>Graph Matches:</strong> ${graphCount}</div>
          <div><strong>Semantic Vector Matches:</strong> ${semanticCount}</div>
          <div><strong>Fused RRF Results:</strong> ${fusedCount}</div>
          <div><strong>Subgraph Paths:</strong> ${pathCount}</div>
        </div>
      </details>
    `;
  }

  container.innerHTML = `
    <div id="answer-container" class="answer-box card">
      <div class="answer-header">
        <div class="answer-title-group">
          <span class="answer-title">Grounded Answer</span>
          <span class="tag tag-blue">Graph RAG + RRF</span>
          ${confTag}
          ${validationBadgeHtml}
        </div>
      </div>

      <div id="answer-text" class="answer-content">
        ${answer}
      </div>

      ${sourcesSectionHtml}
      ${debugTraceHtml}
    </div>
  `;

  // Attach interactive click listeners to source pills for code inspection modal
  container.querySelectorAll(".source-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      const src = pill.dataset.source;
      if (src) {
        state.setSelectedSource(src);
      }
    });
  });
}

export async function handleQuerySubmit() {
  const queryInput = document.getElementById("query-input");
  const queryBtn = document.getElementById("btn-run-query");
  const resultsContainer = document.getElementById("query-results") || document.getElementById("answer-container");

  const question = queryInput ? queryInput.value.trim() : "";
  if (!question) return;

  // Show loading state
  if (queryBtn) {
    queryBtn.disabled = true;
    queryBtn.innerHTML = `<span class="spinner"></span> Reasoning over graph...`;
  }
  if (resultsContainer) {
    resultsContainer.innerHTML = `
      <div class="card" style="display:flex; align-items:center; gap:14px; padding:24px;">
        <span class="spinner" style="width:20px; height:20px; border-width:2px;"></span>
        <div>
          <div style="font-weight:600; color:var(--text-primary); font-size:13.5px;">Reasoning over codebase graph & vector indexes...</div>
          <div style="font-size:12px; color:var(--text-secondary); margin-top:3px;">
            Executing multi-hop retrieval, reciprocal rank fusion, and grounded answer synthesis.
          </div>
        </div>
      </div>
    `;
  }

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

    // Render Answer and citations into resultsContainer
    if (resultsContainer) {
      renderQueryResponse(response, resultsContainer);
    }

    // Render Subgraph visualization if present
    if (Array.isArray(response.graph_paths) && response.graph_paths.length > 0) {
      const graphData = adaptGraphPaths(response.graph_paths);
      if (graphData.nodes.length > 0) {
        updateGraphData(graphData);
      }
    }
  } catch (err) {
    console.error("GRAPH RAG QUERY ERROR:", err);
    if (resultsContainer) {
      resultsContainer.innerHTML = `
        <div class="card" style="border-color: rgba(251, 113, 133, 0.3); background: rgba(251, 113, 133, 0.05); padding:16px;">
          <div class="card-title" style="color:var(--accent-rose);">
            <span>Query Execution Error</span>
            <span class="tag tag-rose">Failed</span>
          </div>
          <div style="font-size:13px; color:var(--text-secondary); line-height:1.55; margin-top:8px;">
            ${escapeHtml(err.message || "An unexpected error occurred while executing the Graph RAG query.")}
          </div>
        </div>
      `;
    }
  } finally {
    if (queryBtn) {
      queryBtn.disabled = false;
      queryBtn.innerHTML = `Run Codebase Query`;
    }
  }
}

export function renderMarkdown(text) {
  if (!text) return "";
  let out = escapeHtml(text);

  // Fenced code blocks with language support
  out = out.replace(/```([a-zA-Z0-9_-]*)\n([\s\S]*?)```/g, (match, lang, code) => {
    return `<pre style="background:var(--bg-elevated); border:1px solid var(--border-color); border-radius:var(--radius-md); padding:10px 14px; margin:10px 0; overflow-x:auto; font-family:var(--font-mono); font-size:12px; line-height:1.5; color:var(--text-primary); white-space:pre;"><code>${code.trim()}</code></pre>`;
  });

  // Inline code
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");

  // Bold
  out = out.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");

  // Headings
  out = out.replace(
    /^#### (.*?)$/gm,
    "<h4 style='color:var(--text-primary); font-size:13px; font-weight:600; margin:12px 0 4px;'>$1</h4>"
  );
  out = out.replace(
    /^### (.*?)$/gm,
    "<h3 style='color:var(--text-primary); font-size:14px; font-weight:600; margin:14px 0 6px;'>$1</h3>"
  );
  out = out.replace(
    /^## (.*?)$/gm,
    "<h2 style='color:var(--text-primary); font-size:15px; font-weight:700; margin:16px 0 8px;'>$1</h2>"
  );

  // Unordered lists
  out = out.replace(/^- (.*?)$/gm, "<li style='margin-left:18px; margin-bottom:4px; list-style-type:disc;'>$1</li>");

  // Numbered lists
  out = out.replace(
    /^\d+\.\s+(.*?)$/gm,
    "<li style='margin-left:18px; margin-bottom:4px; list-style-type:decimal;'>$1</li>"
  );

  // Paragraph breaks
  out = out.replace(/\n\n/g, "<div style='height:8px;'></div>");
  out = out.replace(/\n/g, "<br>");

  return out;
}

export function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

export function escapeAttr(text) {
  if (!text) return "";
  return String(text).replace(/"/g, "&quot;").replace(/'/g, "&#039;");
}
