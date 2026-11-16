/**
 * Code Quality & Security Analysis UI Handler.
 * Displays repository vulnerability summaries, severity breakdown, and evidence-grounded findings.
 */

import { analyzeQualitySecurity } from "./api.js";
import { state } from "./state.js";
import { openSourceModal } from "./ui.js";

let currentFindings = [];
let activeCategoryFilter = "all";
let activeSeverityFilter = "all";
let activeSearchQuery = "";

export function initQualitySecurityView() {
  const runBtn = document.getElementById("btn-run-quality-security");
  const categorySelect = document.getElementById("qs-category-select");

  if (runBtn) {
    runBtn.addEventListener("click", () => handleQualitySecuritySubmit());
  }

  if (categorySelect) {
    categorySelect.addEventListener("change", () => handleQualitySecuritySubmit());
  }
}

export async function handleQualitySecuritySubmit() {
  const runBtn = document.getElementById("btn-run-quality-security");
  const categorySelect = document.getElementById("qs-category-select");
  const resultsContainer = document.getElementById("quality-security-results");

  const repoId = state.selectedRepository || "sample_repo";
  const catChoice = categorySelect ? categorySelect.value : "all";
  const categories = catChoice === "all" ? ["quality", "security"] : [catChoice];

  if (runBtn) {
    runBtn.disabled = true;
    runBtn.innerHTML = `<span class="spinner"></span> Scanning Quality & Security...`;
  }

  try {
    const payload = {
      repository_id: repoId,
      categories: categories,
    };

    const response = await analyzeQualitySecurity(payload);
    state.setQualitySecurityResult(response);
    currentFindings = response.findings || [];

    if (resultsContainer) {
      renderQualitySecurityDashboard(response, resultsContainer);
    }
  } catch (err) {
    if (resultsContainer) {
      resultsContainer.innerHTML = `
        <div class="card error-card">
          <div class="card-title" style="color:var(--accent-rose)">Analysis Failed</div>
          <p style="color:var(--text-secondary); font-size:13px; margin-top:6px;">${escapeHtml(err.message)}</p>
        </div>
      `;
    }
  } finally {
    if (runBtn) {
      runBtn.disabled = false;
      runBtn.innerHTML = `<span>Run Quality & Security Scan</span>`;
    }
  }
}

function renderQualitySecurityDashboard(data, container) {
  const summary = data.summary || {};
  const findings = data.findings || [];

  container.innerHTML = `
    <!-- Top Severity Distribution Statistics Bar -->
    <div class="stat-grid" style="margin-bottom:14px;">
      <div class="stat-box filter-stat-btn" data-severity-filter="Critical" style="cursor:pointer;" title="Filter Critical Issues">
        <span class="stat-label">Critical</span>
        <span class="stat-value" style="color:var(--accent-rose)">${summary.critical_count || 0}</span>
      </div>
      <div class="stat-box filter-stat-btn" data-severity-filter="High" style="cursor:pointer;" title="Filter High Issues">
        <span class="stat-label">High</span>
        <span class="stat-value" style="color:var(--accent-amber)">${summary.high_count || 0}</span>
      </div>
      <div class="stat-box filter-stat-btn" data-severity-filter="Medium" style="cursor:pointer;" title="Filter Medium Issues">
        <span class="stat-label">Medium</span>
        <span class="stat-value" style="color:#facc15">${summary.medium_count || 0}</span>
      </div>
      <div class="stat-box filter-stat-btn" data-severity-filter="Low" style="cursor:pointer;" title="Filter Low Issues">
        <span class="stat-label">Low</span>
        <span class="stat-value" style="color:var(--accent-blue)">${summary.low_count || 0}</span>
      </div>
      <div class="stat-box" title="Total Files Scanned">
        <span class="stat-label">Files Scanned</span>
        <span class="stat-value" style="color:var(--accent-cyan)">${summary.files_scanned || 0}</span>
      </div>
      <div class="stat-box" title="Total Findings">
        <span class="stat-label">Total Findings</span>
        <span class="stat-value" style="color:var(--text-primary)">${summary.total_findings || 0}</span>
      </div>
    </div>

    <!-- AI Security & Quality Health Assessment Card -->
    <div class="card" style="margin-bottom:14px;">
      <div class="card-title">
        <span>Security Posture & Quality Health Assessment</span>
        <span class="tag tag-purple">AI Grounded Report</span>
      </div>
      <div class="markdown-body" style="font-size:13px; line-height:1.6; color:var(--text-secondary); margin-top:10px;">
        ${renderMarkdown(data.explanation || 'Static analysis completed.')}
      </div>
    </div>

    <!-- Interactive Findings Explorer & Filter Bar -->
    <div class="card">
      <div class="card-title" style="flex-wrap:wrap; gap:10px;">
        <span>Findings Explorer (<span id="qs-visible-count">${findings.length}</span> / ${findings.length})</span>
        <div class="filter-controls-group" style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
          <input type="text" id="qs-search-input" class="text-input" placeholder="Filter by file or symbol..." style="width:200px; padding:5px 10px; font-size:12px;">
          <select id="qs-filter-category" class="select-input" style="padding:4px 8px; font-size:12px;">
            <option value="all">All Categories</option>
            <option value="security">Security Only</option>
            <option value="quality">Quality Only</option>
          </select>
          <select id="qs-filter-severity" class="select-input" style="padding:4px 8px; font-size:12px;">
            <option value="all">All Severities</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
      </div>

      <!-- Findings List Container -->
      <div id="qs-findings-list" style="display:flex; flex-direction:column; gap:12px; margin-top:14px;">
        <!-- Rendered dynamically -->
      </div>
    </div>
  `;

  // Attach search and filter event listeners
  const searchInput = document.getElementById("qs-search-input");
  const filterCat = document.getElementById("qs-filter-category");
  const filterSev = document.getElementById("qs-filter-severity");

  if (searchInput) {
    searchInput.addEventListener("input", (e) => {
      activeSearchQuery = e.target.value.trim().toLowerCase();
      applyFilters();
    });
  }

  if (filterCat) {
    filterCat.addEventListener("change", (e) => {
      activeCategoryFilter = e.target.value;
      applyFilters();
    });
  }

  if (filterSev) {
    filterSev.addEventListener("change", (e) => {
      activeSeverityFilter = e.target.value;
      applyFilters();
    });
  }

  // Stat box quick click filters
  container.querySelectorAll(".filter-stat-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const targetSev = btn.dataset.severityFilter;
      if (filterSev) {
        filterSev.value = targetSev;
        activeSeverityFilter = targetSev;
        applyFilters();
      }
    });
  });

  // Initial render of findings
  applyFilters();
}

function applyFilters() {
  const listContainer = document.getElementById("qs-findings-list");
  const visibleCountEl = document.getElementById("qs-visible-count");
  if (!listContainer) return;

  const filtered = currentFindings.filter((f) => {
    // Category match
    if (activeCategoryFilter !== "all" && f.category !== activeCategoryFilter) {
      return false;
    }
    // Severity match
    if (activeSeverityFilter !== "all" && f.severity !== activeSeverityFilter) {
      return false;
    }
    // Search query match
    if (activeSearchQuery) {
      const matchFile = (f.file_path || "").toLowerCase().includes(activeSearchQuery);
      const matchTitle = (f.title || "").toLowerCase().includes(activeSearchQuery);
      const matchRule = (f.rule_id || "").toLowerCase().includes(activeSearchQuery);
      if (!matchFile && !matchTitle && !matchRule) {
        return false;
      }
    }
    return true;
  });

  if (visibleCountEl) {
    visibleCountEl.textContent = filtered.length;
  }

  if (filtered.length === 0) {
    listContainer.innerHTML = `
      <div style="padding:32px 16px; text-align:center; color:var(--text-muted); font-size:13px;">
        <span>🎯 No findings matched the active filter criteria.</span>
      </div>
    `;
    return;
  }

  listContainer.innerHTML = filtered
    .map((f) => {
      const sevClass =
        f.severity === "Critical"
          ? "tag-rose"
          : f.severity === "High"
          ? "tag-amber"
          : f.severity === "Medium"
          ? "tag-yellow"
          : "tag-blue";

      const catTag = f.category === "security" ? "tag-purple" : "tag-emerald";
      const lineStr = f.line_number != null ? `:${f.line_number}` : "";

      return `
      <div class="finding-card-item card" data-finding-id="${escapeAttr(f.id)}" style="background:var(--bg-elevated); border:1px solid var(--border-color); padding:14px; border-radius:6px; cursor:pointer;">
        <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:10px; margin-bottom:8px;">
          <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
            <span class="tag ${sevClass}" style="font-weight:700;">${escapeHtml(f.severity)}</span>
            <span class="tag ${catTag}">${escapeHtml(f.category.toUpperCase())}</span>
            <code style="font-size:11px; color:var(--text-muted);">${escapeHtml(f.rule_id)}</code>
            <strong style="color:var(--text-primary); font-size:13.5px;">${escapeHtml(f.title)}</strong>
          </div>
          <span style="font-size:11px; color:var(--text-muted);">${escapeHtml(f.confidence || 'High')} Confidence</span>
        </div>

        <div style="font-size:12.5px; color:var(--text-secondary); margin-bottom:8px; line-height:1.45;">
          ${escapeHtml(f.explanation)}
        </div>

        <!-- Location with Source Modal Link -->
        <div style="font-size:12px; margin-bottom:8px;">
          <span style="color:var(--text-muted);">Location:</span>
          <a href="#" class="qs-source-link" data-file="${escapeAttr(f.file_path)}" data-line="${f.line_number || 1}" style="color:var(--accent-blue); text-decoration:underline; margin-left:4px;" title="Click to view line in source modal">
            <code>${escapeHtml(f.file_path)}${escapeHtml(lineStr)}</code>
          </a>
        </div>

        <!-- Masked Code Evidence -->
        ${
          f.code_evidence
            ? `
          <div class="code-evidence-box" style="background:#090e18; border:1px solid var(--border-subtle); padding:8px 12px; border-radius:4px; font-family:var(--font-mono); font-size:11.5px; color:#e2e8f0; margin-bottom:8px; overflow-x:auto;">
            <code>${escapeHtml(f.code_evidence)}</code>
          </div>
        `
            : ""
        }

        <!-- Why It Matters Callout -->
        <div style="font-size:12px; background:rgba(251,113,133,0.06); border-left:3px solid var(--accent-rose); padding:6px 10px; border-radius:0 4px 4px 0; margin-bottom:6px; color:var(--text-secondary);">
          <strong style="color:var(--accent-rose);">Why It Matters:</strong> ${escapeHtml(f.why_it_matters)}
        </div>

        <!-- Suggested Remediation -->
        <div style="font-size:12px; background:rgba(45,212,191,0.06); border-left:3px solid var(--accent-emerald); padding:6px 10px; border-radius:0 4px 4px 0; color:var(--text-secondary);">
          <strong style="color:var(--accent-emerald);">Remediation:</strong> ${escapeHtml(f.suggested_remediation)}
        </div>
      </div>
    `;
    })
    .join("");

  // Attach click listeners to source links
  listContainer.querySelectorAll(".qs-source-link").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      const filePath = link.dataset.file;
      const lineNum = parseInt(link.dataset.line, 10) || 1;
      openSourceModal(filePath, lineNum, lineNum);
    });
  });

  // Attach click listeners to findings to update right inspector
  listContainer.querySelectorAll(".finding-card-item").forEach((card) => {
    card.addEventListener("click", () => {
      const fId = card.dataset.findingId;
      const target = currentFindings.find((f) => f.id === fId);
      if (target) {
        state.setSelectedFinding(target);
      }
    });
  });
}

function renderMarkdown(text) {
  if (!text) return "";
  let out = escapeHtml(text);
  out = out.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/^#### (.*?)$/gm, "<h4 style='color:var(--text-primary); font-size:13px; margin:12px 0 4px;'>$1</h4>");
  out = out.replace(/^### (.*?)$/gm, "<h3 style='color:var(--text-primary); font-size:14px; margin:14px 0 6px;'>$1</h3>");
  out = out.replace(/^## (.*?)$/gm, "<h2 style='color:var(--text-primary); font-size:15px; margin:16px 0 8px;'>$1</h2>");
  out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
  out = out.replace(/^- (.*?)$/gm, "<li style='margin-left:18px;'>$1</li>");
  out = out.replace(/^\d+\.\s+(.*?)$/gm, "<li style='margin-left:18px;'>$1</li>");
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
