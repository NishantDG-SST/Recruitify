const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

export async function createJob(payload: { title?: string; raw_text?: string }) {
  const response = await fetch(`${API_BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error("Failed to create job");
  }

  return response.json();
}

export async function fetchJobs() {
  const response = await fetch(`${API_BASE}/jobs`);
  if (!response.ok) throw new Error("Failed to fetch jobs");
  return response.json();
}

export async function fetchCandidates(jobId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates`);
  if (!response.ok) throw new Error("Failed to fetch candidates");
  return response.json();
}

export async function uploadCandidates(jobId: string, files: File[]) {
  const form = new FormData();
  files.forEach((file) => form.append("files", file));

  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates`, {
    method: "POST",
    body: form
  });

  if (!response.ok) {
    throw new Error("Failed to upload candidates");
  }

  return response.json();
}

export async function fetchRankings(jobId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/rankings`);

  if (!response.ok) {
    throw new Error("Failed to fetch rankings");
  }

  return response.json();
}

export async function createOverride(jobId: string, runId: string, payload: { candidate_id: string; old_rank: int; new_rank: int; reason: string }) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/rankings/${runId}/overrides`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    throw new Error("Failed to create override");
  }

  return response.json();
}

export async function generateInterview(jobId: string, candidateId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates/details/${candidateId}/interviews`, {
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Failed to generate interview");
  }

  return response.json();
}
