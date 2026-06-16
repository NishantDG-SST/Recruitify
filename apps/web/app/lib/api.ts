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

export async function generateRankings(jobId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/rankings`, {
    method: "POST"
  });

  if (!response.ok) {
    throw new Error("Failed to generate rankings");
  }

  return response.json();
}

export async function createOverride(jobId: string, runId: string, payload: { candidate_id: string; old_rank: number; new_rank: number; reason: string }) {
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

export async function fetchBiasAnalysis(jobId: string, runId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/rankings/${runId}/bias`);
  if (!response.ok) {
    throw new Error("Failed to fetch bias analysis");
  }
  return response.json();
}

export async function fetchInterviews(jobId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/interviews`);
  if (!response.ok) {
    throw new Error("Failed to fetch interviews");
  }
  return response.json();
}

export async function fetchCandidateRounds(jobId: string, candidateId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates/${candidateId}/rounds`);
  if (!response.ok) {
    throw new Error("Failed to fetch candidate rounds");
  }
  return response.json();
}

export async function fetchCandidateJobProfile(jobId: string, candidateId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates/${candidateId}/profile`);
  if (!response.ok) {
    throw new Error("Failed to fetch candidate job profile");
  }
  return response.json();
}

export async function scheduleInterviewRound(jobId: string, candidateId: string, payload: { round_name: string; interviewer_name?: string; scheduled_at?: string }) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates/${candidateId}/rounds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error("Failed to schedule round");
  }
  return response.json();
}

export async function updateInterviewRound(jobId: string, candidateId: string, roundId: string, payload: { status?: string; feedback?: string }) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates/${candidateId}/rounds/${roundId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) {
    throw new Error("Failed to update round");
  }
  return response.json();
}

export async function updateCandidateStatus(jobId: string, candidateId: string, status: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates/${candidateId}/status`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status })
  });
  if (!response.ok) {
    throw new Error("Failed to update candidate status");
  }
  return response.json();
}

export async function simulateRankings(jobId: string, weights: Record<string, number>) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/rankings/simulate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weights })
  });
  if (!response.ok) {
    throw new Error("Failed to simulate rankings");
  }
  return response.json();
}

export async function deleteCandidate(jobId: string, candidateId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates/${candidateId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete candidate");
  }
  return response.json();
}

export async function clearAllCandidates(jobId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to clear candidates");
  }
  return response.json();
}

export async function deleteJob(jobId: string) {
  const response = await fetch(`${API_BASE}/jobs/${jobId}`, {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error("Failed to delete job");
  }
  return response.json();
}
