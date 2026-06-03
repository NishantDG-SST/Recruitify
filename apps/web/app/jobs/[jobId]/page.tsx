import Link from "next/link";

export default function JobWorkspacePage({ params }: { params: { jobId: string } }) {
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
      </div>
    </div>
  );
}
