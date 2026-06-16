"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { updateCandidateStatus } from "../../lib/api";

/** Returns the candidate's current role/job title for display.
 *  Legacy records may have email or phone stored in the current_role field,
 *  so we filter those out and fall back to "Not Specified". */
function getDisplayRole(role: string | undefined | null): string {
  if (!role || role.trim() === "") return "Not Specified";
  const r = role.trim();
  if (/@/.test(r)) return "Not Specified";
  if (/^\+?[\d\s\-().]{7,}$/.test(r)) return "Not Specified";
  if (/^(email|phone)\s*:/i.test(r)) return "Not Specified";
  if (/email\s*:/i.test(r) || /phone\s*:/i.test(r)) return "Not Specified";
  return r;
}

export default function CandidateProfilePage({ params }: { params: { id: string } }) {
  const [candidate, setCandidate] = useState<any>(null);

  useEffect(() => {
    fetch(`/api/jobs/all/candidates/details/${params.id}`)
      .then(res => res.json())
      .then(data => {
        setCandidate(data);
      })
      .catch(console.error);
  }, [params.id]);

  const handleStatusUpdate = async (newStatus: string) => {
    const jobId = candidate.profile?.job_id || "all";
    try {
      await updateCandidateStatus(jobId, params.id, newStatus);
      setCandidate({ ...candidate, status: newStatus });
      alert(`Candidate status updated to ${newStatus}`);
    } catch (e) {
      alert("Failed to update status");
    }
  };



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
        {/* Candidate Overview Panel */}
        <div className="panel light-orange">
          <h2>Overview</h2>
          <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Candidate ID</div>
              <div style={{ fontSize: '15px', wordBreak: 'break-all' }}>{params.id}</div>
            </div>
            <div>
              <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Current Pipeline Status</div>
              <div style={{ marginTop: '4px' }}>
                <span className="tag" style={{ textTransform: 'uppercase', padding: '6px 12px', background: '#ffe8d6', color: '#b4462f', fontWeight: 800 }}>
                  {candidate.status || 'Active'}
                </span>
              </div>
            </div>

          </div>
        </div>

        {/* Candidate Profile Panel */}
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
                <div style={{ fontSize: '16px', fontWeight: 700 }}>{candidate.profile?.name || 'N/A'}</div>
              </div>
              {candidate.profile?.email && (
                <div>
                  <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Email</div>
                  <div style={{ fontSize: '16px' }}>{candidate.profile.email}</div>
                </div>
              )}
              {candidate.profile?.phone && (
                <div>
                  <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Phone</div>
                  <div style={{ fontSize: '16px' }}>{candidate.profile.phone}</div>
                </div>
              )}
              <div>
                <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase' }}>Current Role</div>
                <div style={{ fontSize: '16px' }}>{getDisplayRole(candidate.profile?.current_role)}</div>
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
                  <pre style={{ background: 'rgba(0,0,0,0.05)', padding: '12px', borderRadius: '8px', whiteSpace: 'pre-wrap', fontSize: '12px', maxHeight: '150px', overflowY: 'auto' }}>
                    {candidate.profile.raw_text}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
        
        {/* AI Score Match Breakdown Panel */}
        {candidate.scores && (
          <div className="panel light-orange" style={{ gridColumn: '1 / -1' }}>
            <h2>AI Match & Score Breakdown</h2>
            <div style={{ marginTop: '20px', display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '20px' }}>
              {[
                { label: "Hard Skills Match", value: candidate.scores.hard_skills, color: '#4361ee', desc: "Alignment of technical skills, tools, and languages with job requirements." },
                { label: "Soft Skills Match", value: candidate.scores.soft_skills, color: '#4cc9f0', desc: "Match of interpersonal and leadership qualities specified in the JD." },
                { label: "Experience Match", value: candidate.scores.experience, color: '#f72585', desc: "Candidate years of experience relative to the requested minimum." },
                { label: "Domain Knowledge Match", value: candidate.scores.domain_knowledge, color: '#7209b7', desc: "Familiarity with industry domains or specialized business sectors." },
              ].map((bar, idx) => (
                <div key={idx} style={{ padding: '16px', background: 'rgba(255,255,255,0.5)', borderRadius: '8px', border: '1px solid rgba(0,0,0,0.05)', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                  <div>
                    <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase', marginBottom: '8px' }}>
                      {bar.label}
                    </div>
                    <div style={{ fontSize: '13px', color: '#555', marginBottom: '16px' }}>
                      {bar.desc}
                    </div>
                  </div>
                  <div>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '6px' }}>
                      <span style={{ fontSize: '24px', fontWeight: 800, color: bar.color }}>
                        {typeof bar.value === 'number' ? `${bar.value.toFixed(0)}%` : '0%'}
                      </span>
                    </div>
                    <div style={{ width: '100%', height: '8px', background: 'rgba(0,0,0,0.06)', borderRadius: '4px', overflow: 'hidden' }}>
                      <div style={{ 
                        width: `${bar.value || 0}%`, 
                        height: '100%', 
                        background: bar.color,
                        borderRadius: '4px',
                        transition: 'width 0.4s ease'
                      }} />
                    </div>
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
