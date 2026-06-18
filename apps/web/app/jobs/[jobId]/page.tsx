"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { deleteJob, fetchJobDetail } from "../../lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

export default function JobWorkspacePage({ params }: { params: { jobId: string } }) {
  const router = useRouter();
  const [clearing, setClearing] = useState(false);
  const [clearStatus, setClearStatus] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [job, setJob] = useState<any>(null);

  useEffect(() => {
    fetchJobDetail(params.jobId).then(setJob).catch(console.error);
  }, [params.jobId]);

  const handleClearAll = async () => {
    if (!confirm("⚠️ This will delete ALL candidates for this job. This cannot be undone. Are you sure?")) return;
    setClearing(true);
    setClearStatus(null);
    try {
      const response = await fetch(`${API_BASE}/jobs/${params.jobId}/candidates`, { method: "DELETE" });
      if (!response.ok) throw new Error("Failed to clear candidates");
      const result = await response.json();
      setClearStatus(`✅ Cleared ${result.deleted_count} candidates successfully.`);
    } catch (e) {
      setClearStatus("❌ Failed to clear candidates.");
    } finally {
      setClearing(false);
    }
  };

  const handleDeleteJob = async () => {
    if (!confirm("⚠️ Delete this job? This will permanently remove all candidates, rankings, and interviews. This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteJob(params.jobId);
      router.push("/jobs");
    } catch (e) {
      alert("❌ Failed to delete job.");
      setDeleting(false);
    }
  };

  return (
    <div className="hero">
      <div>
        <span className="badge">Job workspace</span>
        <h1>{job?.title || "Job Dashboard"}</h1>
        <p>
          Upload resumes, watch parsing progress, and review the ranked shortlist
          with evidence.
        </p>
        {job?.summary && (
          <div style={{
            marginTop: '16px',
            background: 'rgba(255,255,255,0.6)',
            borderLeft: '5px solid #7209b7',
            borderRadius: '12px',
            padding: '16px 20px'
          }}>
            <div style={{ fontSize: '11px', fontWeight: 800, textTransform: 'uppercase', letterSpacing: '1px', color: '#7209b7', marginBottom: '6px' }}>
              AI Job Summary
            </div>
            <p style={{ margin: 0, fontSize: '14px', lineHeight: 1.7, color: 'var(--text-main)' }}>
              {job.summary}
            </p>
          </div>
        )}
      </div>
      <div className="panel">
        <h2>Actions</h2>
        <div className="list">
          <Link className="row" href={`/jobs/${params.jobId}/candidates`}>
            <strong>Upload candidates</strong>
            <span>Batch ingestion for this specific job</span>
          </Link>
          <Link className="row" href={`/jobs/${params.jobId}/rankings`}>
            <strong>View rankings</strong>
            <span>Evidence + bias review</span>
          </Link>
        </div>
        <div style={{ marginTop: '20px', borderTop: '1px solid rgba(0,0,0,0.05)', paddingTop: '16px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <button 
            className="pill-button" 
            onClick={handleClearAll}
            disabled={clearing}
            style={{ background: '#d90429', color: '#fff', fontSize: '12px' }}
          >
            {clearing ? "Clearing..." : "Clear All Candidates"}
          </button>
          {clearStatus && (
            <div style={{ fontSize: '13px', fontWeight: 600 }}>
              {clearStatus}
            </div>
          )}
          <button 
            className="pill-button" 
            onClick={handleDeleteJob}
            disabled={deleting}
            style={{ background: '#1a1a2e', color: '#fff', fontSize: '12px' }}
          >
            {deleting ? "Deleting Job..." : "🗑️ Delete This Job"}
          </button>
        </div>
      </div>
    </div>
  );
}
