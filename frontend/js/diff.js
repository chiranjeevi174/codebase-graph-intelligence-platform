/**
 * Structural Git Diff Analysis UI Handler.
 */

import { analyzeStructuralDiff } from "./api.js";
import { state } from "./state.js";

export function initDiffView() {
  const diffBtn = document.getElementById("btn-run-diff");

  if (diffBtn) {
    diffBtn.addEventListener("click", () => handleDiffSubmit());
  }
}

export async function handleDiffSubmit() {
  const baseRefInput = document.getElementById("diff-base-input");
  const targetRefInput = document.getElementById("diff-target-input");
  const diffBtn = document.getElementById("btn-run-diff");
  const diffResultsContainer = document.getElementById("diff-results");

  const baseRef = baseRefInput ? baseRefInput.value.trim() : "HEAD~1";
  const targetRef = targetRefInput ? targetRefInput.value.trim() : "HEAD";

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

      const fileItems = (response.affected_files || []).map(f => `<div class="tree-node"><span>${f}</span><span class="tag tag-blue">Modified File</span></div>`).join("");
      const symDiffs = (response.symbol_diffs || []).map(sd => `
        <div class="tree-node">
          <div>
            <strong>${sd.symbol_name || sd.symbol_id}</strong> (${sd.change_type || 'MODIFIED'})
            <div style="font-size:11px; color:var(--text-muted)">File: ${sd.file_path || 'N/A'}</div>
          </div>
          <span class="tag tag-purple">${sd.change_type || 'CHANGE'}</span>
        </div>
      `).join("");

      const sigChanges = (response.signature_changes || []).map(sig => `
        <div class="card" style="margin-top:8px;">
          <div style="font-weight:600; font-size:12px; color:var(--accent-amber)">
            Signature Change: ${sig.symbol_name}
          </div>
          <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted)">
            <div><strong>Before:</strong> ${sig.old_signature || 'N/A'}</div>
            <div><strong>After:</strong> ${sig.new_signature || 'N/A'}</div>
            <div><strong>Params Added:</strong> ${(sig.added_parameters || []).join(', ') || 'None'}</div>
            <div><strong>Params Removed:</strong> ${(sig.removed_parameters || []).join(', ') || 'None'}</div>
          </div>
        </div>
      `).join("");

      diffResultsContainer.innerHTML = `
        <div class="card">
          <div class="card-title">
            <span>Structural Git Diff (${baseRef} → ${targetRef})</span>
            <span class="tag ${riskTag}">Classification: ${riskClass}</span>
          </div>
          <div style="font-size:13px; color:var(--text-secondary)">
            ${response.explanation || 'Structural changes analyzed across AST and Code Graph.'}
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
      diffResultsContainer.innerHTML = `<span style="color:var(--accent-rose)">Structural Diff Analysis Failed: ${err.message}</span>`;
    }
  } finally {
    if (diffBtn) {
      diffBtn.disabled = false;
      diffBtn.innerHTML = `Analyze Structural Diff`;
    }
  }
}
