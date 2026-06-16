"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { fetchCandidates, fetchJobs } from "../lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

async function uploadSingleCandidate(jobId: string, file: File) {
  const form = new FormData();
  form.append("files", file);
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

/** Returns the candidate's current role/job title for display.
 *  Legacy records may have email or phone stored in the current_role field,
 *  so we filter those out and fall back to "Not Specified". */
function getDisplayRole(role: string | undefined | null): string {
  if (!role || role.trim() === "") return "Not Specified";
  const r = role.trim();
  // Reject values that look like email addresses
  if (/@/.test(r)) return "Not Specified";
  // Reject values that look like phone numbers (digit-heavy)
  if (/^\+?[\d\s\-().]{7,}$/.test(r)) return "Not Specified";
  // Reject values that start with "Email:" or "Phone:" (old format)
  if (/^(email|phone)\s*:/i.test(r)) return "Not Specified";
  // Reject values that contain "Email:" or "Phone:" substrings (pipe-separated old format)
  if (/email\s*:/i.test(r) || /phone\s*:/i.test(r)) return "Not Specified";
  return r;
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
    const total = files.length;
    let successCount = 0;
    const failedFiles: string[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      setUploadProgress(`Processing ${i + 1} of ${total}: ${file.name}`);
      try {
        await uploadSingleCandidate(selectedJob, file);
        successCount++;
      } catch (err: any) {
        console.error(`Upload failed for ${file.name}:`, err);
        failedFiles.push(file.name);
      }
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

  return (
    <>
      <h1 className="page-title">Candidate Directory</h1>
      <p className="page-subtitle">Manage and review all uploaded resumes.</p>

      <div className="stats-grid">
        <div className="stat-card purple">
          <div className="stat-title">Total Candidates</div>
          <div className="stat-value">{candidates.length}</div>
        </div>
        <div className="stat-card orange">
          <div className="stat-title">In Pipeline</div>
          <div className="stat-value">{candidates.filter(c => c.status === 'processing').length}</div>
        </div>
        <div className="stat-card pink">
          <div className="stat-title">Placed</div>
          <div className="stat-value">0</div>
        </div>
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2>All Candidates</h2>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <select 
              className="search-bar" 
              style={{ padding: '10px 16px', borderRadius: '24px', border: '1px solid #ccc' }}
              value={selectedJob} 
              onChange={e => setSelectedJob(e.target.value)}
            >
              <option value="" disabled>Select Job</option>
              {jobs.map(job => (
                <option key={job.id} value={job.id}>{job.title}</option>
              ))}
            </select>
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
              disabled={isUploading}
            >
              {isUploading ? "Uploading..." : "Upload Resumes (Batch)"}
            </button>
          </div>
        </div>
        
        <div className="ranking-list">
          {isLoading && <p>Loading candidates...</p>}
          {!isLoading && candidates.length === 0 && <p>No candidates found in the database.</p>}
          {!isLoading && candidates.map(c => (
            <div className="ranking-item" key={c.id}>
              <div className="ranking-avatar"></div>
              <div className="ranking-info">
                <div className="ranking-name">{c.name} <span className="tag" style={{ marginLeft: 8 }}>{c.id.slice(0,8)}</span></div>
                <div className="ranking-desc">{getDisplayRole(c.role)} • Uploaded {new Date(c.created_at).toLocaleDateString()}</div>
              </div>
              <div className="tag">{c.status}</div>
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
          ))}
        </div>
      </div>
    </>
  );
}
