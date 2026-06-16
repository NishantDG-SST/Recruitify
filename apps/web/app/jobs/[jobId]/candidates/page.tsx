"use client";

import { useState, useRef } from "react";

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

export default function CandidateUploadPage({ params }: { params: { jobId: string } }) {
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResults, setUploadResults] = useState<{ success: number; failed: string[] } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const submitFiles = async () => {
    if (!files.length) {
      setStatus("Select one or more resumes first");
      return;
    }
    setIsUploading(true);
    setUploadResults(null);
    setStatus(`Uploading and processing ${files.length} resumes...`);
    let successCount = 0;
    const failedFiles: string[] = [];

    try {
      await uploadMultipleCandidates(params.jobId, files);
      successCount = files.length;
    } catch (err: any) {
      console.error("Batch upload failed:", err);
      files.forEach(f => failedFiles.push(f.name));
    }

    setStatus(null);
    setUploadResults({ success: successCount, failed: failedFiles });
    setIsUploading(false);
    setFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <div className="card-grid">
      <div className="panel">
        <h2>Batch upload</h2>
        <div className="list">
          <input
            className="input"
            type="file"
            multiple
            ref={fileInputRef}
            onChange={(event) => setFiles(Array.from(event.target.files || []))}
          />
          <button className="button" onClick={submitFiles} disabled={isUploading}>
            {isUploading ? "Uploading..." : "Upload resumes"}
          </button>
          <button className="button secondary">Link external source</button>
          
          {/* Progress indicator */}
          {status && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px' }}>
              <div style={{ width: '16px', height: '16px', border: '2px solid #b4462f', borderTop: '2px solid transparent', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
              <span style={{ fontWeight: 700, color: '#b4462f' }}>{status}</span>
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
            </div>
          )}

          {/* Results banner */}
          {uploadResults && (
            <div style={{ 
              marginTop: '12px',
              background: uploadResults.failed.length === 0 ? '#d4edda' : '#fff3cd', 
              border: `1px solid ${uploadResults.failed.length === 0 ? '#28a745' : '#ffc107'}`, 
              borderRadius: '8px', 
              padding: '12px' 
            }}>
              <div style={{ fontWeight: 700, color: uploadResults.failed.length === 0 ? '#155724' : '#856404' }}>
                ✅ {uploadResults.success} candidate{uploadResults.success !== 1 ? 's' : ''} uploaded successfully
                {uploadResults.failed.length > 0 && ` | ❌ ${uploadResults.failed.length} failed`}
              </div>
              {uploadResults.failed.length > 0 && (
                <div style={{ fontSize: '12px', color: '#856404', marginTop: '4px' }}>
                  Failed files: {uploadResults.failed.join(', ')}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
      <div className="panel">
        <h2>Batch status</h2>
        <div className="list">
          <div className="row">
            <strong>Upload Progress</strong>
            <span>{isUploading ? status : (uploadResults ? `${uploadResults.success} processed` : "Ready")}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
