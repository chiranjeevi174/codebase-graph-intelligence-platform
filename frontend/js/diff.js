/**
 * Structural Git Diff Analysis UI Handler.
 * Formats AST signature modifications, changed symbols, and affected files.
 */

import { analyzeStructuralDiff } from "./api.js";
import { state } from "./state.js";

export function initDiffView() {
  const diffBtn = document.getElementById("btn-run-diff");
  const baseInput = document.getElementById("diff-base-input");
  const targetInput = document.getElementById("diff-target-input");

  if (diffBtn) {
    diffBtn.addEventListener("click", () => handleDiffSubmit());
  }

  if (baseInput) {
    baseInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleDiffSubmit();
      }
    });
  }

  if (targetInput) {
    targetInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleDiffSubmit();
      }
    });
  }
}

export async function handleDiffSubmit() {
  const baseRefInput = document.getElementById("diff-base-input");
  const targetRefInput = document.getElementById("diff-target-input");
  const diffBtn = document.getElementById("btn-run-diff");
  const diffResultsContainer = document.getElementById("diff-results");

  const baseRef = baseRefInput ? baseRefInput.value.trim() : "HEAD~1";
  const targetRef = targetRefInput ? targetRefInput.value.trim() : "HEAD";

  if (!baseRef || !targetRef) return;

  if (diffBtn) {
    diffBtn.disabled = true;
    diffBtn.innerHTML = `<span class="spinner"></span> Comparing Commits...`;
  }

  try {
    const payload = {
      repository_id: state.selectedRepository || "default",
      base_ref: baseRef,
      target_ref: targetRef,
      max_hops: 3,
    };

    const response = await analyzeStructuralDiff(payload);
    state.setDiffResult(response);

    if (diffResultsContainer) {
      const riskClass = response.classification || "LOW";
      const riskTag = riskClass === "HIGH" ? "tag-rose" : riskClass === "MEDIUM" ? "tag-amber" : "tag-emerald";

      const fileItems = (response.affected_files || []).map(f => `
        <div class="tree-node">
          <span><code>${escapeHtml(f)}</code></span>
          <span class="tag tag-blue">Modified File</span>
        </div>
      `).join("");

      const symDiffs = (response.symbol_diffs || []).map(sd => `
        <div class="tree-node">
          <div>
            <strong>${escapeHtml(sd.symbol_name || sd.symbol_id)}</strong> (${escapeHtml(sd.change_type || 'MODIFIED')})
            <div style="font-size:11px; color:var(--text-muted)">File: ${escapeHtml(sd.file_path || 'N/A')}</div>
          </div>
          <span class="tag tag-purple">${escapeHtml(sd.change_type || 'CHANGE')}</span>
        </div>
      `).join("");

      const sigChanges = (response.signature_changes || []).map(sig => `
        <div class="card" style="margin-top:8px;">
          <div style="font-weight:600; font-size:12px; color:var(--accent-amber)">
            Signature Change: <code>${escapeHtml(sig.symbol_name)}</code>
          </div>
          <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted); margin-top:4px; display:flex; flex-direction:column; gap:3px;">
            <div><strong>Before:</strong> <code>${escapeHtml(sig.old_signature || 'N/A')}</code></div>
            <div><strong>After:</strong> <code>${escapeHtml(sig.new_signature || 'N/A')}</code></div>
            <div><strong>Params Added:</strong> ${escapeHtml((sig.added_parameters || []).join(', ') || 'None')}</div>
            <div><strong>Params Removed:</strong> ${escapeHtml((sig.removed_parameters || []).join(', ') || 'None')}</div>
          </div>
        </div>
      `).join("");

      diffResultsContainer.innerHTML = `
        <div class="card">
          <div class="card-title">
            <span>Structural Git Diff (<code>${escapeHtml(baseRef)}</code> → <code>${escapeHtml(targetRef)}</code>)</span>
            <span class="tag ${riskTag}">Impact Risk: ${escapeHtml(riskClass)}</span>
          </div>
          <div style="font-size:13px; color:var(--text-secondary); line-height:1.5;">
            ${escapeHtml(response.explanation || 'Structural changes analyzed across AST signatures and Code Graph.')}
          </div>
        </div>

        <div class="card">
          <div class="card-title">Affected Files (${(response.affected_files || []).length})</div>
          ${fileItems || '<div style="color:var(--text-muted); font-size:12px;">No affected files found</div>'}
        </div>

        <div class="card">
          <div class="card-title">Changed Symbols (${(response.symbol_diffs || []).length})</div>
          ${symDiffs || '<div style="color:var(--text-muted); font-size:12px;">No structural symbol changes</div>'}
        </div>

        ${sigChanges}
      `;
    }

  } catch (err) {
    if (diffResultsContainer) {
      diffResultsContainer.innerHTML = `
        <div class="card" style="border-color:rgba(244,63,94,0.3);">
          <div class="card-title" style="color:var(--accent-rose);">Structural Diff Analysis Failed</div>
          <div style="color:var(--text-secondary); font-size:13px;">
            ${escapeHtml(err?.message || String(err))}
          </div>
        </div>
      `;
    }
  } finally {
    if (diffBtn) {
      diffBtn.disabled = false;
      diffBtn.innerHTML = `Analyze Structural Diff`;
    }
  }
}

function escapeHtml(text) {
  if (!text) return "";
  if (typeof text === "object") {
    try {
      text = JSON.stringify(text);
    } catch {
      return "—";
    }
  }
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
