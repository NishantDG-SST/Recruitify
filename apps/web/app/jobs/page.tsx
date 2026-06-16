"use client";

import { useState, useEffect } from "react";
import { createJob, fetchJobs, deleteJob, fetchJobDetail, clearAllCandidates } from "../lib/api";
import Link from "next/link";

export default function JobsPage() {
  const [title, setTitle] = useState("");
  const [rawText, setRawText] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState<any | null>(null);
  const [jobLoading, setJobLoading] = useState(false);

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

  const handleOpenJobProfile = async (jobId: string) => {
    try {
      setJobLoading(true);
      const data = await fetchJobDetail(jobId);
      setSelectedJob(data);
    } catch (e) {
      console.error(e);
      alert("Error loading job profile details");
    } finally {
      setJobLoading(false);
    }
  };

  const handleClearCandidates = async (jobId: string) => {
    if (!confirm("⚠️ Are you sure you want to delete all candidates uploaded for this job? This will also clear all candidate rankings and interviews. This cannot be undone.")) return;
    try {
      setStatus("Clearing candidates...");
      await clearAllCandidates(jobId);
      setStatus("✅ All candidates cleared successfully.");
      alert("Candidates cleared successfully!");
    } catch (e) {
      console.error(e);
      setStatus("❌ Failed to clear candidates.");
      alert("Error clearing candidates");
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
                    <button 
                      className="pill-button"
                      onClick={() => handleOpenJobProfile(job.id)}
                      disabled={jobLoading}
                      style={{ background: 'rgba(180, 70, 47, 0.05)', color: '#b4462f', borderColor: 'rgba(180, 70, 47, 0.2)' }}
                    >
                      View Job Profile
                    </button>
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

      {/* Job Profile Detail Modal */}
      {selectedJob && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          width: '100%',
          height: '100%',
          background: 'rgba(0, 0, 0, 0.6)',
          backdropFilter: 'blur(8px)',
          zIndex: 9999,
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          animation: 'fadeIn 0.2s ease-out'
        }}>
          <div style={{
            background: '#fff',
            width: '90%',
            maxWidth: '700px',
            maxHeight: '90vh',
            borderRadius: '24px',
            boxShadow: '0 20px 50px rgba(0, 0, 0, 0.15)',
            border: '1px solid rgba(0, 0, 0, 0.05)',
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            animation: 'scaleUp 0.3s cubic-bezier(0.16, 1, 0.3, 1)'
          }}>
            {/* Header */}
            <div style={{
              padding: '24px 32px',
              borderBottom: '1px solid rgba(0, 0, 0, 0.06)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: 'linear-gradient(135deg, #fdfbf7 0%, #f5efe6 100%)'
            }}>
              <div>
                <h2 style={{ margin: 0, fontSize: '20px', fontWeight: 800, color: '#1a1a1a' }}>
                  Job Requirements Summary
                </h2>
                <div style={{ fontSize: '13px', color: '#666', marginTop: '4px' }}>
                  Role: <strong>{selectedJob.title}</strong>
                </div>
              </div>
              <button
                onClick={() => setSelectedJob(null)}
                style={{
                  border: 'none',
                  background: 'rgba(0, 0, 0, 0.05)',
                  cursor: 'pointer',
                  width: '36px',
                  height: '36px',
                  borderRadius: '50%',
                  display: 'flex',
                  justifyContent: 'center',
                  alignItems: 'center',
                  fontSize: '18px',
                  fontWeight: 600,
                  color: '#666',
                  transition: 'background 0.2s'
                }}
              >
                ✕
              </button>
            </div>

            {/* Scrollable Body */}
            <div style={{ padding: '32px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
              
              {/* Description Summary */}
              <div>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '14px', fontWeight: 800, color: '#1a1a1a' }}>Structured Job Summary</h4>
                <p style={{ margin: 0, fontSize: '13px', color: '#555', lineHeight: '1.6', background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid rgba(0,0,0,0.03)' }}>
                  {selectedJob.parsed_json?.summary || "No automated summary extracted."}
                </p>
              </div>

              {/* Skills requirements */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid rgba(0,0,0,0.03)' }}>
                  <h5 style={{ margin: '0 0 10px 0', fontSize: '13px', fontWeight: 800, color: '#2d6a4f' }}>
                    🔥 Must-Have Skills
                  </h5>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {selectedJob.parsed_json?.must_have_skills?.length > 0 ? (
                      selectedJob.parsed_json.must_have_skills.map((skill: string, i: number) => (
                        <span key={i} style={{ fontSize: '10px', background: '#d8f3dc', color: '#1b4332', padding: '3px 8px', borderRadius: '4px', fontWeight: 700 }}>
                          {skill}
                        </span>
                      ))
                    ) : (
                      <span style={{ fontSize: '12px', color: '#666', fontStyle: 'italic' }}>None listed.</span>
                    )}
                  </div>
                </div>

                <div style={{ background: '#f8fafc', padding: '16px', borderRadius: '12px', border: '1px solid rgba(0,0,0,0.03)' }}>
                  <h5 style={{ margin: '0 0 10px 0', fontSize: '13px', fontWeight: 800, color: '#0369a1' }}>
                    💡 Nice-to-Have Skills
                  </h5>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                    {selectedJob.parsed_json?.nice_to_have_skills?.length > 0 ? (
                      selectedJob.parsed_json.nice_to_have_skills.map((skill: string, i: number) => (
                        <span key={i} style={{ fontSize: '10px', background: '#e0f2fe', color: '#0369a1', padding: '3px 8px', borderRadius: '4px', fontWeight: 700 }}>
                          {skill}
                        </span>
                      ))
                    ) : (
                      <span style={{ fontSize: '12px', color: '#666', fontStyle: 'italic' }}>None listed.</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Other requirements */}
              <div style={{ background: '#fcfcfc', padding: '20px', borderRadius: '12px', border: '1px solid rgba(0,0,0,0.04)', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '13px' }}>
                <div>
                  <span style={{ color: '#666', fontWeight: 500 }}>Min. Experience Required:</span>
                  <div style={{ fontWeight: 700, color: '#1a1a1a', marginTop: '2px' }}>
                    {selectedJob.parsed_json?.years_experience_min || 0} Years
                  </div>
                </div>

                <div>
                  <span style={{ color: '#666', fontWeight: 500 }}>Preferred Education:</span>
                  <div style={{ fontWeight: 700, color: '#1a1a1a', marginTop: '2px' }}>
                    {selectedJob.parsed_json?.education_level || "Not Specified"}
                  </div>
                </div>

                <div style={{ gridColumn: 'span 2' }}>
                  <span style={{ color: '#666', fontWeight: 500 }}>Target Domains:</span>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', marginTop: '4px' }}>
                    {selectedJob.parsed_json?.domains?.length > 0 ? (
                      selectedJob.parsed_json.domains.map((dom: string, i: number) => (
                        <span key={i} style={{ background: '#fae8ff', color: '#86198f', padding: '2px 8px', borderRadius: '4px', fontSize: '10px', fontWeight: 600 }}>
                          {dom}
                        </span>
                      ))
                    ) : 'Not Specified'}
                  </div>
                </div>
              </div>

            </div>

            {/* Footer with Delete and Clear Candidates actions */}
            <div style={{
              padding: '20px 32px',
              borderTop: '1px solid rgba(0, 0, 0, 0.06)',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              background: '#fafafa'
            }}>
              <div style={{ display: 'flex', gap: '12px' }}>
                <button
                  onClick={() => {
                    handleDeleteJob(selectedJob.id, selectedJob.title);
                    setSelectedJob(null);
                  }}
                  style={{
                    background: '#d90429',
                    color: '#fff',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '10px',
                    fontSize: '12px',
                    fontWeight: 800,
                    cursor: 'pointer'
                  }}
                >
                  Delete Requisition
                </button>
                <button
                  onClick={() => handleClearCandidates(selectedJob.id)}
                  style={{
                    background: '#f77f00',
                    color: '#fff',
                    border: 'none',
                    padding: '10px 20px',
                    borderRadius: '10px',
                    fontSize: '12px',
                    fontWeight: 800,
                    cursor: 'pointer'
                  }}
                >
                  Clear Candidates
                </button>
              </div>

              <button
                onClick={() => setSelectedJob(null)}
                style={{
                  background: '#1a1a1a',
                  color: '#fff',
                  border: 'none',
                  padding: '10px 20px',
                  borderRadius: '10px',
                  fontSize: '12px',
                  fontWeight: 800,
                  cursor: 'pointer'
                }}
              >
                Close
              </button>
            </div>
          </div>

          <style>{`
            @keyframes fadeIn {
              from { opacity: 0; }
              to { opacity: 1; }
            }
            @keyframes scaleUp {
              from { transform: scale(0.95); opacity: 0; }
              to { transform: scale(1); opacity: 1; }
            }
          `}</style>
        </div>
      )}
    </>
  );
}
