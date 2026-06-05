"use client";

import { useState, useEffect } from "react";
import { createJob, fetchJobs, deleteJob } from "../lib/api";
import Link from "next/link";

export default function JobsPage() {
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [jobs, setJobs] = useState<any[]>([]);

  useEffect(() => {
    loadJobs();
  }, []);

  const loadJobs = async () => {
    try {
      const data = await fetchJobs();
      setJobs(data.jobs || []);
    } catch (e) {
      console.error("Failed to load jobs", e);
    }
  };

  const submitJob = async () => {
    try {
      setStatus("Submitting...");
      const response = await createJob({ title, raw_text: rawText });
      setStatus(`Created job ${response.job_id}`);
      setTitle("");
      setRawText("");
      loadJobs();
    } catch (error) {
      setStatus("Failed to create job");
    }
  };

  const handleDeleteJob = async (jobId: string, jobTitle: string) => {
    if (!confirm(`⚠️ Delete "${jobTitle}"? This will permanently remove all candidates, rankings, and interviews for this job. This cannot be undone.`)) return;
    try {
      setStatus("Deleting job...");
      await deleteJob(jobId);
      setStatus(`✅ Job deleted successfully.`);
      loadJobs();
    } catch (e) {
      setStatus("❌ Failed to delete job.");
    }
  };

  return (
    <>
      <h1 className="page-title">Job Postings</h1>
      <p className="page-subtitle">Upload requirements and manage open requisitions.</p>

      <div className="content-grid">
        <div className="panel light-orange">
          <h2>Create New Job</h2>
          <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <input
              className="search-bar"
              style={{ width: '100%', background: 'rgba(255,255,255,0.8)' }}
              placeholder="Role Title (e.g. Senior Backend Engineer)"
              value={title}
              onChange={(event) => setTitle(event.target.value)}
            />
            <textarea
              className="search-bar"
              style={{ width: '100%', minHeight: '180px', borderRadius: '16px', padding: '16px', background: 'rgba(255,255,255,0.8)', resize: 'vertical' }}
              placeholder="Paste the unstructured Job Description here..."
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
            />
            <button className="pill-button" style={{ padding: '12px 24px', fontSize: '14px', alignSelf: 'flex-start' }} onClick={submitJob}>
              Extract Requirements
            </button>
            {status ? <span style={{ fontWeight: 800, marginTop: '8px' }}>{status}</span> : null}
          </div>
        </div>

        <div className="panel green">
          <h2>Active Requisitions</h2>
          <div className="ranking-list" style={{ marginTop: '20px' }}>
            {jobs.length === 0 && <p style={{ fontSize: '14px', color: '#555' }}>No active jobs found. Create one to get started!</p>}
            {jobs.map(job => (
              <div className="ranking-item" key={job.id}>
                <div className="ranking-info">
                  <div className="ranking-name">{job.title}</div>
                  <div className="ranking-desc">{new Date(job.created_at).toLocaleDateString()}</div>
                </div>
                {job.status === "processing" ? (
                  <div className="tag">Processing JD</div>
                ) : (
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <Link href={`/jobs/${job.id}/rankings`}>
                      <button className="pill-button">View Rankings</button>
                    </Link>
                    <button
                      className="pill-button"
                      onClick={() => handleDeleteJob(job.id, job.title)}
                      style={{ background: '#d90429', color: '#fff', fontSize: '12px' }}
                    >
                      Delete
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
