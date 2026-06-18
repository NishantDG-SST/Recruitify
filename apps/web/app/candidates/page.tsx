"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { fetchCandidates, fetchJobs } from "../lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

async function uploadMultipleCandidates(jobId: string, files: File[]) {
  const form = new FormData();
  files.forEach(file => form.append("files", file));
  const response = await fetch(`${API_BASE}/jobs/${jobId}/candidates`, {
    method: "POST",
    body: form,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `HTTP ${response.status}`);
  }
  return response.json();
}

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [uploadResults, setUploadResults] = useState<{ success: number; failed: string[] } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadCandidates = (jobId: string) => {
    const targetJob = jobId || "all";
    fetchCandidates(targetJob).then(data => {
      setCandidates(data.candidates || []);
      setIsLoading(false);
    }).catch(e => {
      console.error(e);
      setIsLoading(false);
    });
  };
  
  const loadJobs = () => {
    fetchJobs().then(data => {
      setJobs(data.jobs || []);
      if (data.jobs && data.jobs.length > 0 && !selectedJob) {
        setSelectedJob(data.jobs[0].id);
      }
    }).catch(e => console.error(e));
  }

  useEffect(() => {
    loadJobs();
  }, []);

  useEffect(() => {
    if (selectedJob) {
      setIsLoading(true);
      loadCandidates(selectedJob);
    }
  }, [selectedJob]);

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    if (!selectedJob) {
      alert("Please select a job before uploading.");
      return;
    }
    setIsUploading(true);
    setUploadResults(null);
    const files = Array.from(e.target.files);
    setUploadProgress(`Uploading and processing ${files.length} resumes...`);
    let successCount = 0;
    const failedFiles: string[] = [];

    try {
      await uploadMultipleCandidates(selectedJob, files);
      successCount = files.length;
    } catch (err: any) {
      console.error("Batch upload failed:", err);
      files.forEach(f => failedFiles.push(f.name));
    }

    setUploadProgress(null);
    setUploadResults({ success: successCount, failed: failedFiles });
    setIsUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    // Reload candidates list
    loadCandidates(selectedJob);
  };

  const handleDeleteCandidate = async (candidateId: string) => {
    if (!confirm("Are you sure you want to delete this candidate?")) return;
    try {
      const response = await fetch(`${API_BASE}/jobs/${selectedJob}/candidates/${candidateId}`, {
        method: "DELETE",
      });
      if (!response.ok) throw new Error("Delete failed");
      loadCandidates(selectedJob);
    } catch (e) {
      alert("Failed to delete candidate");
    }
  };

  const initials = (name: string) => (name || "?").split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
  const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
    selected: { bg: "#d8f3dc", color: "#1b4332" },
    rejected: { bg: "#fde2e4", color: "#721c24" },
    interviewing: { bg: "#e7d3ff", color: "#5a189a" },
    interview: { bg: "#e7d3ff", color: "#5a189a" },
    extracted: { bg: "#ffe8d6", color: "#b4462f" },
    processing: { bg: "#fff3cd", color: "#856404" },
  };
  const statusStyle = (s: string) => STATUS_STYLES[s] || { bg: "rgba(56,18,11,0.08)", color: "#755f58" };
  const inInterviewCount = candidates.filter(c => ["interview", "interviewing"].includes(c.status)).length;
  const selectedCount = candidates.filter(c => c.status === "selected").length;
  const selectedJobObj = jobs.find(j => j.id === selectedJob);

  return (
    <>
      <h1 className="page-title">Candidate Directory</h1>
      <p className="page-subtitle">Manage and review all uploaded resumes{selectedJobObj ? ` for ${selectedJobObj.title}` : ""}.</p>

      <div className="stats-grid">
        <div className="stat-card purple">
          <div className="stat-title">👥 Total Candidates</div>
          <div className="stat-value">{candidates.length}</div>
          <div className="stat-trend">{selectedJobObj ? selectedJobObj.title : "All jobs"}</div>
        </div>
        <div className="stat-card orange">
          <div className="stat-title">🎙️ In Interview</div>
          <div className="stat-value">{inInterviewCount}</div>
          <div className="stat-trend">Currently interviewing</div>
        </div>
        <div className="stat-card pink">
          <div className="stat-title">✅ Selected</div>
          <div className="stat-value">{selectedCount}</div>
          <div className="stat-trend">Offers extended</div>
        </div>
      </div>

      {/* Job switcher */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontWeight: 900, fontSize: 11, letterSpacing: 1, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 10 }}>
          Jobs
        </div>
        {jobs.length === 0 ? (
          <div className="ranking-item" style={{ maxWidth: 320 }}>
            <div className="ranking-info"><div className="ranking-desc">No jobs yet. Create a job to begin.</div></div>
          </div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            {jobs.map(job => {
              const active = selectedJob === job.id;
              return (
                <button
                  key={job.id}
                  onClick={() => setSelectedJob(job.id)}
                  style={{
                    textAlign: "left", cursor: "pointer", minWidth: 200,
                    border: "none", borderLeft: `6px solid ${active ? "#ff7d29" : "transparent"}`,
                    borderRadius: 16, padding: "14px 18px",
                    background: active ? "var(--card-light-orange)" : "rgba(56,18,11,0.05)",
                    boxShadow: active ? "0 6px 16px rgba(255,123,41,0.25)" : "none",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 16 }}>💼</span>
                    <span style={{ fontWeight: 800, fontSize: 15, color: "var(--text-main)" }}>{job.title}</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 700, marginTop: 4 }}>
                    {job.created_at ? `Created ${new Date(job.created_at).toLocaleDateString()}` : ""}
                    {active ? "  ·  ● Active" : ""}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Upload Progress Banner */}
      {uploadProgress && (
        <div style={{ background: '#fff3cd', border: '1px solid #ffc107', borderRadius: '12px', padding: '16px 20px', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{ width: '20px', height: '20px', border: '3px solid #b4462f', borderTop: '3px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
          <span style={{ fontWeight: 700, color: '#856404' }}>{uploadProgress}</span>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      )}

      {/* Upload Results Banner */}
      {uploadResults && (
        <div style={{ 
          background: uploadResults.failed.length === 0 ? '#d4edda' : '#fff3cd', 
          border: `1px solid ${uploadResults.failed.length === 0 ? '#28a745' : '#ffc107'}`, 
          borderRadius: '12px', 
          padding: '16px 20px', 
          marginBottom: '20px' 
        }}>
          <div style={{ fontWeight: 700, color: uploadResults.failed.length === 0 ? '#155724' : '#856404', marginBottom: uploadResults.failed.length > 0 ? '8px' : '0' }}>
            ✅ {uploadResults.success} candidate{uploadResults.success !== 1 ? 's' : ''} uploaded successfully
            {uploadResults.failed.length > 0 && ` | ❌ ${uploadResults.failed.length} failed`}
          </div>
          {uploadResults.failed.length > 0 && (
            <div style={{ fontSize: '12px', color: '#856404' }}>
              Failed files: {uploadResults.failed.join(', ')}
            </div>
          )}
          <button 
            onClick={() => setUploadResults(null)} 
            style={{ marginTop: '8px', background: 'none', border: 'none', color: '#666', cursor: 'pointer', fontSize: '12px', textDecoration: 'underline' }}
          >
            Dismiss
          </button>
        </div>
      )}

      <div className="panel light-orange">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: 12 }}>
          <h2 style={{ margin: 0 }}>All Candidates {candidates.length > 0 && <span className="tag" style={{ fontSize: 12 }}>{candidates.length}</span>}</h2>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <input
              type="file"
              multiple
              ref={fileInputRef}
              onChange={handleFileChange}
              style={{ display: 'none' }}
              accept=".pdf,.txt,.docx"
            />
            <button
              className="pill-button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading || !selectedJob}
              style={{ background: '#7209b7', color: '#fff', padding: '10px 20px' }}
            >
              {isUploading ? "Uploading..." : "⬆ Upload Resumes (Batch)"}
            </button>
          </div>
        </div>

        <div className="ranking-list">
          {isLoading && <p style={{ color: '#6b5a52' }}>Loading candidates...</p>}
          {!isLoading && candidates.length === 0 && (
            <div style={{ textAlign: "center", padding: "40px 24px", border: "2px dashed rgba(56,18,11,0.18)", borderRadius: 20, background: "rgba(255,255,255,0.4)" }}>
              <div style={{ fontSize: 40 }}>📄</div>
              <p style={{ color: "#6b5a52", fontWeight: 800, fontSize: 15, margin: "8px 0 0" }}>No candidates yet</p>
              <p style={{ color: "#8a7a72", margin: "4px 0 0" }}>Upload resumes for this job to populate the directory.</p>
            </div>
          )}
          {!isLoading && candidates.map(c => {
            const ss = statusStyle(c.status);
            return (
              <div className="ranking-item" key={c.id}>
                <div className="ranking-avatar" style={{ display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 900, color: "#fff", fontSize: 15 }}>
                  {initials(c.name)}
                </div>
                <div className="ranking-info">
                  <div className="ranking-name">{c.name} <span className="tag" style={{ marginLeft: 8, fontSize: 10 }}>{c.id.slice(0, 8)}</span></div>
                  <div className="ranking-desc">{c.role} • Uploaded {new Date(c.created_at).toLocaleDateString()}</div>
                </div>
                <span className="tag" style={{ textTransform: "uppercase", fontSize: 10, fontWeight: 800, background: ss.bg, color: ss.color }}>{c.status}</span>
                <Link href={`/candidates/${c.id}`}>
                  <button className="pill-button" style={{ marginLeft: '12px', background: 'var(--bg-page)', color: 'var(--text-main)' }}>
                    View Profile
                  </button>
                </Link>
                <button
                  className="pill-button"
                  onClick={() => handleDeleteCandidate(c.id)}
                  style={{ marginLeft: '8px', background: '#d90429', color: '#fff', fontSize: '11px', padding: '6px 12px' }}
                >
                  Delete
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
