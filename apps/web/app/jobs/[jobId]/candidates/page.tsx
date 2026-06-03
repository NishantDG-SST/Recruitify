"use client";

import { useState } from "react";

import { uploadCandidates } from "../../../lib/api";

export default function CandidateUploadPage({ params }: { params: { jobId: string } }) {
  const [files, setFiles] = useState<File[]>([]);
  const [status, setStatus] = useState<string | null>(null);

  const submitFiles = async () => {
    try {
      if (!files.length) {
        setStatus("Select one or more resumes first");
        return;
      }
      setStatus("Uploading...");
      const response = await uploadCandidates(params.jobId, files);
      setStatus(`Batch ${response.batch_id} submitted`);
      setFiles([]);
    } catch (error) {
      setStatus("Failed to upload candidates");
    }
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
            onChange={(event) => setFiles(Array.from(event.target.files || []))}
          />
          <button className="button" onClick={submitFiles}>
            Upload resumes
          </button>
          <button className="button secondary">Link external source</button>
          {status ? <span>{status}</span> : null}
        </div>
      </div>
      <div className="panel">
        <h2>Batch status</h2>
        <div className="list">
          <div className="row">
            <strong>Batch 2024-06-03</strong>
            <span>Parsing 14 of 20</span>
          </div>
          <div className="row">
            <strong>Batch 2024-06-02</strong>
            <span>Ranking ready</span>
          </div>
        </div>
      </div>
    </div>
  );
}
