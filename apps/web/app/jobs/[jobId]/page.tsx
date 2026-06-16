"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { deleteJob } from "../../lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api";

export default function JobWorkspacePage({ params }: { params: { jobId: string } }) {
  const router = useRouter();
  const [clearing, setClearing] = useState(false);
  const [clearStatus, setClearStatus] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);

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
        <h1>Job Dashboard</h1>
        <p>
          Upload resumes, watch parsing progress, and review the ranked shortlist
          with evidence.
        </p>
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
