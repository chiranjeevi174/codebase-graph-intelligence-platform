/**
 * PR Analysis UI Handler with SSE Real-time Updates and Polling Fallback.
 * Formats pull request impact, changed symbols, signature diffs, and analysis history.
 */

import { state } from "./state.js";

export function initPRView() {
  const prBtn = document.getElementById("btn-run-pr");

  if (prBtn) {
    prBtn.addEventListener("click", () => handlePRSubmit());
  }
}

export async function handlePRSubmit() {
  const providerInput = document.getElementById("pr-provider-input");
  const repoInput = document.getElementById("pr-repo-input");
  const prNumInput = document.getElementById("pr-num-input");
  const baseInput = document.getElementById("pr-base-input");
  const targetInput = document.getElementById("pr-target-input");
  const dryRunInput = document.getElementById("pr-dryrun-input");
  const prBtn = document.getElementById("btn-run-pr");
  const prResultsContainer = document.getElementById("pr-results");

  const provider = providerInput ? providerInput.value : "github";
  const repo = repoInput ? repoInput.value.trim() : "sample_repo";
  const prNum = prNumInput ? parseInt(prNumInput.value, 10) : 1;
  const baseRef = baseInput ? baseInput.value.trim() : "HEAD~1";
  const targetRef = targetInput ? targetInput.value.trim() : "HEAD";
  const dryRun = dryRunInput ? dryRunInput.checked : true;

  if (prBtn) {
    prBtn.disabled = true;
    prBtn.innerHTML = `<span class="spinner"></span> Submitting PR Analysis Job...`;
  }

  try {
    const payload = {
      provider: provider,
      repository: repo,
      pr_number: prNum,
      repo_path: repo.includes("/") ? null : `tests/fixtures/${repo || state.selectedRepository || 'sample_repo'}`,
      base_ref: baseRef,
      target_ref: targetRef,
      dry_run: dryRun,
      max_hops: 3,
    };

    const res = await fetch("/analysis/pr", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `PR Analysis submission failed: ${res.statusText}`);
    }

    const jobData = await res.json();
    const jobId = jobData.job_id;

    if (prResultsContainer) {
      prResultsContainer.innerHTML = `
        <div class="card">
          <div class="card-title">
            <span>Async PR Job: <code>${escapeHtml(jobId)}</code></span>
            <span id="job-status-badge" class="tag tag-purple">${escapeHtml(jobData.status || 'QUEUED')}</span>
          </div>
          <div style="font-size:13px; color:var(--text-secondary); margin-top:8px;">
            Job queued for background processing. Receiving real-time SSE stream...
          </div>
        </div>
      `;
    }

    // SSE Connection with polling fallback
    let finalJob = jobData;
    let jobStatus = jobData.status || "QUEUED";

    await new Promise((resolve) => {
      let resolved = false;

      const finishStream = (job) => {
        if (resolved) return;
        resolved = true;
        finalJob = job;
        jobStatus = job.status;
        resolve();
      };

      try {
        const evtSource = new EventSource(`/jobs/${jobId}/events`);

        evtSource.onmessage = (event) => {
          try {
            const currentJob = JSON.parse(event.data);
            const badge = document.getElementById("job-status-badge");
            if (badge) {
              badge.textContent = currentJob.status;
              badge.className = currentJob.status === "RUNNING" ? "tag tag-emerald" : "tag tag-purple";
            }

            if (["COMPLETED", "FAILED", "DEAD_LETTER", "CANCELLED"].includes(currentJob.status)) {
              evtSource.close();
              finishStream(currentJob);
            }
          } catch (_) {}
        };

        evtSource.onerror = () => {
          evtSource.close();
          // Fallback to polling loop
          (async () => {
            while (!resolved && (jobStatus === "QUEUED" || jobStatus === "RUNNING")) {
              await new Promise((r) => setTimeout(r, 1000));
              const sRes = await fetch(`/jobs/${jobId}`);
              if (sRes.ok) {
                const polledJob = await sRes.json();
                jobStatus = polledJob.status;
                if (["COMPLETED", "FAILED", "DEAD_LETTER", "CANCELLED"].includes(jobStatus)) {
                  finishStream(polledJob);
                  break;
                }
              }
            }
          })();
        };
      } catch (err) {
        // Direct polling fallback
        (async () => {
          while (!resolved && (jobStatus === "QUEUED" || jobStatus === "RUNNING")) {
            await new Promise((r) => setTimeout(r, 1000));
            const sRes = await fetch(`/jobs/${jobId}`);
            if (sRes.ok) {
              const polledJob = await sRes.json();
              jobStatus = polledJob.status;
              if (["COMPLETED", "FAILED", "DEAD_LETTER", "CANCELLED"].includes(jobStatus)) {
                finishStream(polledJob);
                break;
              }
            }
          }
        })();
      }
    });

    if (jobStatus === "FAILED" || jobStatus === "DEAD_LETTER") {
      if (prResultsContainer) {
        prResultsContainer.innerHTML = `
          <div class="card" style="border-color:rgba(244,63,94,0.3);">
            <div class="card-title">
              <span>PR Analysis Job (<code>${escapeHtml(jobId)}</code>)</span>
              <span class="tag tag-rose">${escapeHtml(jobStatus)}</span>
            </div>
            <div style="font-size:13px; color:var(--accent-rose); margin-top:8px;">
              Job failed: ${escapeHtml(finalJob.error || 'Execution encountered an unrecoverable error.')}
            </div>
            <div style="margin-top:12px;">
              <button id="btn-retry-job-${jobId}" class="btn btn-secondary">Retry Job</button>
            </div>
          </div>
        `;
        const retryBtn = document.getElementById(`btn-retry-job-${jobId}`);
        if (retryBtn) {
          retryBtn.addEventListener("click", async () => {
            retryBtn.disabled = true;
            retryBtn.textContent = "Retrying...";
            try {
              const rRes = await fetch(`/jobs/${jobId}/retry`, { method: "POST" });
              if (!rRes.ok) throw new Error("Retry request failed");
              handlePRSubmit();
            } catch (rErr) {
              alert(`Retry failed: ${rErr.message}`);
            }
          });
        }
      }
      return;
    }

    // Fetch result report
    const resultRes = await fetch(`/jobs/${jobId}/result`);
    if (!resultRes.ok) {
      throw new Error(`Failed to fetch job result: ${resultRes.statusText}`);
    }

    const response = await resultRes.json();

    // Fetch history
    let historyItems = [];
    try {
      const histRes = await fetch(`/analysis/pr/${provider}/${encodeURIComponent(repo)}/${prNum}/history`);
      if (histRes.ok) {
        historyItems = await histRes.json();
      }
    } catch (_) {}

    if (prResultsContainer) {
      const summary = response.summary || {};
      const fileItems = (response.changed_files || []).map((f) => `
        <div class="tree-node">
          <span><code>${escapeHtml(f)}</code></span>
          <span class="tag tag-blue">Changed File</span>
        </div>
      `).join("");

      const symItems = (response.changed_symbols || []).map((s) => `
        <div class="tree-node">
          <div>
            <strong>${escapeHtml(s.symbol_name || s.qualified_name)}</strong>
            <div style="font-size:11px; color:var(--text-muted)">File: ${escapeHtml(s.file_path || 'N/A')}</div>
          </div>
          <span class="tag tag-purple">${escapeHtml(s.change_type || 'MODIFIED')}</span>
        </div>
      `).join("");

      const historyRows = (historyItems || []).slice(0, 5).map((h) => `
        <tr>
          <td><code>${escapeHtml(h.analysis_run_id)}</code></td>
          <td><code>${escapeHtml((h.head_sha || '').substring(0, 7))}</code></td>
          <td><span class="tag ${h.status === 'COMPLETED' ? 'tag-emerald' : 'tag-rose'}">${escapeHtml(h.status)}</span></td>
          <td>${escapeHtml(h.comment_status || 'NOT_REQUESTED')}</td>
        </tr>
      `).join("");

      prResultsContainer.innerHTML = `
        <div class="card">
          <div class="card-title">
            <span>PR #${response.pr_number} Analysis (${escapeHtml(response.provider).toUpperCase()})</span>
            <span class="tag tag-emerald">Job: ${escapeHtml(jobId)}</span>
          </div>
          <div style="font-size:13px; color:var(--text-secondary); line-height:1.5;">
            ${escapeHtml(response.explanation || 'Pull request structural analysis compiled.')}
          </div>
          <table class="kv-table">
            <tr><td class="kv-key">Job ID</td><td class="kv-val">${escapeHtml(jobId)}</td></tr>
            <tr><td class="kv-key">Job Status</td><td class="kv-val">COMPLETED</td></tr>
            <tr><td class="kv-key">Worker ID</td><td class="kv-val">${escapeHtml(finalJob.worker_id || 'worker_local')}</td></tr>
            <tr><td class="kv-key">Execution Duration</td><td class="kv-val">${finalJob.duration_ms ? finalJob.duration_ms + ' ms' : 'N/A'}</td></tr>
            <tr><td class="kv-key">Comment Status</td><td class="kv-val">${escapeHtml(finalJob.comment_status || 'NOT_REQUESTED')}</td></tr>
            <tr><td class="kv-key">Changed Files</td><td class="kv-val">${summary.changed_files_count || 0}</td></tr>
            <tr><td class="kv-key">Changed Symbols</td><td class="kv-val">${summary.changed_symbols_count || 0}</td></tr>
            <tr><td class="kv-key">Signature Changes</td><td class="kv-val">${summary.signature_changes_count || 0}</td></tr>
            <tr><td class="kv-key">API Changes</td><td class="kv-val">${summary.api_changes_count || 0}</td></tr>
            <tr><td class="kv-key">Affected Files</td><td class="kv-val">${summary.affected_files_count || 0}</td></tr>
            <tr><td class="kv-key">Cross-Language Impacts</td><td class="kv-val">${summary.cross_language_impacts_count || 0}</td></tr>
          </table>
        </div>

        ${historyRows ? `
        <div class="card">
          <div class="card-title">PR Analysis History</div>
          <table class="kv-table" style="font-size:12px;">
            <thead>
              <tr style="text-align:left; color:var(--text-muted);">
                <th>Run ID</th>
                <th>Head SHA</th>
                <th>Status</th>
                <th>Comment State</th>
              </tr>
            </thead>
            <tbody>
              ${historyRows}
            </tbody>
          </table>
        </div>
        ` : ''}

        <div class="card">
          <div class="card-title">Changed Symbols</div>
          ${symItems || '<div style="color:var(--text-muted); font-size:12px;">No structural symbol changes</div>'}
        </div>

        <div class="card">
          <div class="card-title">Changed Files</div>
          ${fileItems || '<div style="color:var(--text-muted); font-size:12px;">No changed files</div>'}
        </div>
      `;
    }
  } catch (err) {
    if (prResultsContainer) {
      prResultsContainer.innerHTML = `
        <div class="card" style="border-color:rgba(244,63,94,0.3);">
          <div class="card-title" style="color:var(--accent-rose);">PR Analysis Failed</div>
          <div style="color:var(--text-secondary); font-size:13px;">
            ${escapeHtml(err?.message || String(err))}
          </div>
        </div>
      `;
    }
  } finally {
    if (prBtn) {
      prBtn.disabled = false;
      prBtn.innerHTML = `Analyze Pull Request`;
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
