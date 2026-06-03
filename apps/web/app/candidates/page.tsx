"use client";

import Link from "next/link";
import { useState, useEffect, useRef } from "react";
import { fetchCandidates, uploadCandidates, fetchJobs } from "../lib/api";

export default function CandidatesPage() {
  const [candidates, setCandidates] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState<string>("");
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
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
    const files = Array.from(e.target.files);
    try {
      await uploadCandidates(selectedJob, files);
      loadCandidates(selectedJob);
    } catch (err) {
      console.error("Upload failed", err);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
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
                <div className="ranking-desc">{c.role} • Uploaded {new Date(c.created_at).toLocaleDateString()}</div>
              </div>
              <div className="tag">{c.status}</div>
              <Link href={`/candidates/${c.id}`}>
                <button className="pill-button" style={{ marginLeft: '12px', background: 'var(--bg-page)', color: 'var(--text-main)' }}>
                  View Profile
                </button>
              </Link>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
