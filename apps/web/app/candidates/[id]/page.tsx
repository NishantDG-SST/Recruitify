"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function CandidateProfilePage({ params }: { params: { id: string } }) {
  const [candidate, setCandidate] = useState<any>(null);

  useEffect(() => {
    // Basic mock fetch for now, since the UI expects a backend route
    fetch(`/api/jobs/all/candidates/details/${params.id}`)
      .then(res => res.json())
      .then(data => setCandidate(data))
      .catch(console.error);
  }, [params.id]);

  if (!candidate) return <div style={{ padding: 40 }}>Loading profile...</div>;

  return (
    <>
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '20px' }}>
        <Link href="/candidates">
          <button className="pill-button" style={{ background: 'var(--bg-page)', color: 'var(--text-main)' }}>
            ← Back
          </button>
        </Link>
        <h1 className="page-title" style={{ margin: 0 }}>Candidate Profile</h1>
      </div>
      
      <div className="content-grid">
        <div className="panel light-orange">
          <h2>Overview</h2>
          <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Candidate ID</div>
              <div style={{ fontSize: '18px' }}>{params.id}</div>
            </div>
            <div>
              <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Status</div>
              <div className="tag">{candidate.status || 'Active'}</div>
            </div>
          </div>
        </div>
        <div className="panel green">
          <h2>Extracted Profile</h2>
          {candidate.status === 'processing' ? (
            <p style={{ marginTop: '16px', color: '#555' }}>
              The Intelligence Worker is currently processing this candidate's resume to extract skills, experience, and generate vector embeddings.
            </p>
          ) : (
            <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Name</div>
                <div style={{ fontSize: '16px' }}>{candidate.profile?.name || 'N/A'}</div>
              </div>
              <div>
                <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Current Role</div>
                <div style={{ fontSize: '16px' }}>{candidate.profile?.current_role || 'N/A'}</div>
              </div>
              <div>
                <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Skills & Domains</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '4px' }}>
                  {[...(candidate.profile?.skills || []), ...(candidate.profile?.soft_skills || []), ...(candidate.profile?.domains || [])].map((skill: string, i: number) => (
                    <span key={i} className="tag">{skill}</span>
                  ))}
                  {[...(candidate.profile?.skills || []), ...(candidate.profile?.soft_skills || []), ...(candidate.profile?.domains || [])].length === 0 && <span style={{ color: '#555' }}>No skills extracted.</span>}
                </div>
              </div>
              {candidate.profile?.raw_text && (
                <div>
                  <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase', marginBottom: '8px' }}>Resume Excerpt</div>
                  <pre style={{ background: 'rgba(0,0,0,0.05)', padding: '12px', borderRadius: '8px', whiteSpace: 'pre-wrap', fontSize: '12px', maxHeight: '200px', overflowY: 'auto' }}>
                    {candidate.profile.raw_text}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
        
        {candidate.questions && candidate.questions.length > 0 && (
          <div className="panel light-orange" style={{ gridColumn: '1 / -1' }}>
            <h2>AI Generated Interview Questions</h2>
            <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {candidate.questions.map((q: any, i: number) => (
                <div key={i} style={{ padding: '16px', background: 'rgba(255,255,255,0.5)', borderRadius: '8px', border: '1px solid rgba(0,0,0,0.05)' }}>
                  <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase', marginBottom: '8px' }}>
                    {q.category.replace('_', ' ')} • Target Skill: {q.target_skill}
                  </div>
                  <div style={{ fontSize: '16px', fontWeight: 600, marginBottom: '8px' }}>
                    {q.prompt}
                  </div>
                  <div style={{ fontSize: '14px', color: '#555' }}>
                    <span style={{ fontWeight: 600 }}>Rationale:</span> {q.rationale}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </>
  );
}
