/**
 * API Service Layer - Interacts directly with FastAPI backend routes.
 */

const API_BASE = ""; // Relative path to current host (FastAPI server)

export async function fetchHealthStatus() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.statusText}`);
  return await res.json();
}

export async function fetchRepositories() {
  const res = await fetch(`${API_BASE}/repositories`);
  if (!res.ok) throw new Error(`Fetching repositories failed: ${res.statusText}`);
  return await res.json();
}

export async function ingestRepository(params) {
  const res = await fetch(`${API_BASE}/repositories/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Ingestion failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function executeQuery(payload) {
  const res = await fetch(`${API_BASE}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Query failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function fetchGraphData(repositoryId, limit = 150) {
  const res = await fetch(`${API_BASE}/graph/${encodeURIComponent(repositoryId)}?limit=${limit}`);
  if (!res.ok) throw new Error(`Fetching graph summary failed: ${res.statusText}`);
  return await res.json();
}

export async function analyzeImpact(payload) {
  const res = await fetch(`${API_BASE}/analysis/impact`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Impact analysis failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function analyzeApiFlow(payload) {
  const res = await fetch(`${API_BASE}/analysis/api-flow`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `API Flow analysis failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function analyzeStructuralDiff(payload) {
  const res = await fetch(`${API_BASE}/analysis/diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Structural diff failed: ${res.statusText}`);
  }
  return await res.json();
}

export async function fetchSourceCode(filePath, repositoryId = null) {
  let url = `${API_BASE}/source?file_path=${encodeURIComponent(filePath)}`;
  if (repositoryId) {
    url += `&repository_id=${encodeURIComponent(repositoryId)}`;
  }
  const res = await fetch(url);
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || `Source retrieval failed: ${res.statusText}`);
  }
  return await res.json();
}
