"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchCandidateRounds, scheduleInterviewRound, updateInterviewRound, updateCandidateStatus, generateInterview } from "../../lib/api";

export default function CandidateProfilePage({ params }: { params: { id: string } }) {
  const [candidate, setCandidate] = useState<any>(null);
  const [rounds, setRounds] = useState<any[]>([]);
  const [newRoundName, setNewRoundName] = useState("Technical Interview");
  const [newInterviewer, setNewInterviewer] = useState("");
  const [newScheduledAt, setNewScheduledAt] = useState("");
  const [feedbackRoundId, setFeedbackRoundId] = useState<string | null>(null);
  const [roundFeedback, setRoundFeedback] = useState("");
  const [roundStatus, setRoundStatus] = useState("passed");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [movedToInterview, setMovedToInterview] = useState(false);

  const loadRounds = async (jobId: string) => {
    try {
      const data = await fetchCandidateRounds(jobId, params.id);
      setRounds(data || []);
    } catch (e) {
      console.error("Failed to load rounds", e);
    }
  };

  useEffect(() => {
    fetch(`/api/jobs/all/candidates/details/${params.id}`)
      .then(res => res.json())
      .then(data => {
        setCandidate(data);
        const jobId = data.profile?.job_id || "all";
        loadRounds(jobId);
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

  const handleMoveToInterview = async () => {
    const jobId = candidate.profile?.job_id || "all";
    try {
      setStatusMessage("Updating candidate status...");
      await updateCandidateStatus(jobId, params.id, "interviewing");

      setStatusMessage("Scheduling screening round...");
      await scheduleInterviewRound(jobId, params.id, {
        round_name: "Screening",
        interviewer_name: "TBD",
        scheduled_at: new Date().toISOString()
      });

      setStatusMessage("Generating tailored interview questions...");
      await generateInterview(jobId, params.id);

      setMovedToInterview(true);
      setCandidate({ ...candidate, status: "interviewing" });
      loadRounds(jobId);

      // Reload full candidate details to get generated questions
      const updatedRes = await fetch(`/api/jobs/${jobId}/candidates/details/${params.id}`);
      if (updatedRes.ok) {
        const updated = await updatedRes.json();
        setCandidate(updated);
      }

      setStatusMessage(null);
      alert("✅ Candidate moved to Interview Hub and Screening round scheduled!");
    } catch (e) {
      console.error(e);
      alert("❌ Error moving candidate to interview. Please try again.");
      setStatusMessage(null);
    }
  };

  const handleScheduleRound = async (e: React.FormEvent) => {
    e.preventDefault();
    const jobId = candidate.profile?.job_id || "all";
    try {
      await scheduleInterviewRound(jobId, params.id, {
        round_name: newRoundName,
        interviewer_name: newInterviewer || undefined,
        scheduled_at: newScheduledAt ? new Date(newScheduledAt).toISOString() : undefined
      });
      setNewInterviewer("");
      setNewScheduledAt("");
      loadRounds(jobId);
      alert("Interview round scheduled successfully!");
    } catch (e) {
      alert("Failed to schedule round");
    }
  };

  const handleUpdateRoundSubmit = async (roundId: string) => {
    const jobId = candidate.profile?.job_id || "all";
    try {
      await updateInterviewRound(jobId, params.id, roundId, {
        status: roundStatus,
        feedback: roundFeedback
      });
      setFeedbackRoundId(null);
      setRoundFeedback("");
      loadRounds(jobId);
      alert("Round feedback and status updated!");
    } catch (e) {
      alert("Failed to update round feedback");
    }
  };

  const handleGenerateQuestions = async () => {
    const jobId = candidate.profile?.job_id || "all";
    try {
      setStatusMessage("Generating tailored interview questions...");
      const response = await fetch(`/api/jobs/${jobId}/candidates/details/${params.id}/interviews`, {
        method: "POST"
      });
      if (response.ok) {
        const result = await response.json();
        alert(`Successfully generated ${result.questions_generated} questions!`);
        // Reload details
        const detailsRes = await fetch(`/api/jobs/${jobId}/candidates/details/${params.id}`);
        if (detailsRes.ok) {
          const updated = await detailsRes.json();
          setCandidate(updated);
        }
      } else {
        alert("Failed to generate questions");
      }
    } catch (e) {
      console.error(e);
      alert("Error generating questions");
    } finally {
      setStatusMessage(null);
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

            {/* Candidate Progression Action Panel */}
            <div style={{ marginTop: '10px' }}>
              <div style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '12px', textTransform: 'uppercase', marginBottom: '8px' }}>Pipeline Controls</div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                <button 
                  className="pill-button" 
                  onClick={handleMoveToInterview}
                  disabled={movedToInterview || candidate.status === 'interview' || candidate.status === 'interviewing'}
                  style={{ 
                    background: (movedToInterview || candidate.status === 'interview' || candidate.status === 'interviewing') ? '#e2e8f0' : '#2d6a4f', 
                    color: (movedToInterview || candidate.status === 'interview' || candidate.status === 'interviewing') ? '#64748b' : '#fff',
                    cursor: (movedToInterview || candidate.status === 'interview' || candidate.status === 'interviewing') ? 'not-allowed' : 'pointer'
                  }}
                >
                  {(movedToInterview || candidate.status === 'interview' || candidate.status === 'interviewing') ? '✓ In Interview' : 'Move to Interview Hub'}
                </button>
                <button 
                  className="pill-button" 
                  style={{ background: '#52b788', color: '#fff' }}
                  onClick={() => handleStatusUpdate('selected')}
                >
                  Offer / Select Candidate
                </button>
                <button 
                  className="pill-button" 
                  style={{ background: '#d90429', color: '#fff' }}
                  onClick={() => handleStatusUpdate('rejected')}
                >
                  Reject Candidate
                </button>
                <button 
                  className="pill-button" 
                  style={{ background: '#7209b7', color: '#fff' }}
                  onClick={handleGenerateQuestions}
                >
                  Generate Interview Questions
                </button>
                {statusMessage && (
                  <div style={{ fontSize: '12px', color: '#7209b7', fontWeight: 'bold', marginTop: '4px' }}>
                    {statusMessage}
                  </div>
                )}
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

        {/* AI Generated Question Bank */}
        <div className="panel light-orange" style={{ gridColumn: '1 / -1' }}>
          <h2>AI Generated Interview Questions</h2>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
            .loading-spinner {
              border: 4px solid rgba(0, 0, 0, 0.1);
              width: 36px;
              height: 36px;
              border-radius: 50%;
              border-left-color: #7209b7;
              animation: spin 1s linear infinite;
              margin-bottom: 12px;
            }
          `}</style>
          <div style={{ marginTop: '20px' }}>
            {statusMessage ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 0' }}>
                <div className="loading-spinner"></div>
                <div style={{ fontWeight: 700, color: '#7209b7' }}>Generating tailored questions...</div>
              </div>
            ) : candidate.questions && candidate.questions.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                {candidate.questions.map((q: any, i: number) => (
                  <div key={i} style={{ padding: '16px', background: '#fff', borderRadius: '8px', border: '1px solid rgba(0,0,0,0.05)', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                      <span style={{ fontWeight: 800, color: '#7209b7', fontSize: '12px' }}>Q{i + 1}</span>
                      <span style={{ fontWeight: 800, color: 'var(--text-muted)', fontSize: '10px', textTransform: 'uppercase' }}>
                        {q.category.replace('_', ' ')} • Target: {q.target_skill}
                      </span>
                    </div>
                    <div style={{ fontSize: '15px', fontWeight: 600, marginBottom: '8px', color: '#1b4332' }}>
                      {q.prompt}
                    </div>
                    <div style={{ fontSize: '13px', color: '#555' }}>
                      <strong>Rationale:</strong> {q.rationale}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '40px 0', border: '2px dashed rgba(0,0,0,0.1)', borderRadius: '12px', background: 'rgba(255,255,255,0.3)' }}>
                <p style={{ color: '#555', marginBottom: '16px', fontWeight: 600 }}>No interview questions generated yet for this candidate.</p>
                <button 
                  className="pill-button" 
                  style={{ background: '#7209b7', color: '#fff', padding: '10px 24px' }}
                  onClick={handleGenerateQuestions}
                >
                  Generate Interview Questions
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Scheduling & Interview rounds */}
        <div className="panel green" style={{ gridColumn: '1 / -1' }}>
          <h2>Interview Round History</h2>
          
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginTop: '20px' }}>
            {/* List Rounds */}
            <div>
              <h3>Rounds Scheduled</h3>
              {rounds.length === 0 ? (
                <p style={{ fontStyle: 'italic', color: '#666', marginTop: '10px' }}>No rounds scheduled yet for this candidate.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '10px' }}>
                  {rounds.map((round) => (
                    <div key={round.id} style={{ background: '#fff', border: '1px solid #c7f9cc', padding: '12px', borderRadius: '6px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <strong style={{ color: '#1b4332' }}>{round.round_name}</strong>
                        <span className="tag" style={{ textTransform: 'uppercase', fontSize: '10px' }}>{round.status}</span>
                      </div>
                      <div style={{ fontSize: '12px', color: '#666', marginTop: '4px' }}>
                        Interviewer: {round.interviewer_name || "Unassigned"} | Date: {round.scheduled_at ? new Date(round.scheduled_at).toLocaleString() : "TBD"}
                      </div>
                      {round.feedback && (
                        <div style={{ background: '#e9f5ed', padding: '8px', borderRadius: '4px', marginTop: '8px', fontSize: '12px', color: '#333' }}>
                          <strong>Feedback:</strong> {round.feedback}
                        </div>
                      )}
                      
                      {round.status === 'scheduled' && (
                        <button 
                          className="pill-button" 
                          style={{ marginTop: '8px', fontSize: '11px', padding: '4px 10px' }}
                          onClick={() => {
                            setFeedbackRoundId(round.id);
                            setRoundStatus(round.status === 'scheduled' ? 'passed' : round.status);
                          }}
                        >
                          Log Feedback / Result
                        </button>
                      )}

                      {/* Log Feedback Popup/Form inline */}
                      {feedbackRoundId === round.id && (
                        <div style={{ marginTop: '12px', borderTop: '1px solid #ccc', paddingTop: '12px' }}>
                          <div style={{ marginBottom: '8px' }}>
                            <label style={{ fontSize: '12px', fontWeight: 700 }}>Outcome Status:</label>
                            <select 
                              style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #ccc', marginTop: '4px' }}
                              value={roundStatus} 
                              onChange={(e) => setRoundStatus(e.target.value)}
                            >
                              <option value="passed">Passed</option>
                              <option value="failed">Failed</option>
                              <option value="completed">Completed (Other)</option>
                            </select>
                          </div>
                          <div style={{ marginBottom: '8px' }}>
                            <label style={{ fontSize: '12px', fontWeight: 700 }}>Feedback/Notes:</label>
                            <textarea 
                              style={{ width: '100%', padding: '6px', borderRadius: '4px', border: '1px solid #ccc', marginTop: '4px', fontSize: '12px' }}
                              rows={3} 
                              placeholder="Write interviewer notes..."
                              value={roundFeedback} 
                              onChange={(e) => setRoundFeedback(e.target.value)}
                            />
                          </div>
                          <div style={{ display: 'flex', gap: '8px' }}>
                            <button 
                              className="pill-button"
                              onClick={() => handleUpdateRoundSubmit(round.id)}
                            >
                              Save Feedback
                            </button>
                            <button 
                              className="pill-button" 
                              style={{ background: '#eee', color: '#333' }}
                              onClick={() => setFeedbackRoundId(null)}
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      )}

                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Schedule Form */}
            <div>
              <h3>Schedule a New Round</h3>
              <form onSubmit={handleScheduleRound} style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 700 }}>Round Type / Name:</label>
                  <select 
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #ccc', marginTop: '4px' }}
                    value={newRoundName} 
                    onChange={(e) => setNewRoundName(e.target.value)}
                  >
                    <option value="Phone Screening">Phone Screening</option>
                    <option value="Technical Interview">Technical Interview</option>
                    <option value="Behavioral Interview">Behavioral Interview</option>
                    <option value="Manager Round">Manager Round</option>
                  </select>
                </div>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 700 }}>Interviewer Name:</label>
                  <input 
                    type="text" 
                    placeholder="e.g. John Doe"
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #ccc', marginTop: '4px' }}
                    value={newInterviewer} 
                    onChange={(e) => setNewInterviewer(e.target.value)}
                  />
                </div>
                <div>
                  <label style={{ fontSize: '12px', fontWeight: 700 }}>Scheduled Date & Time:</label>
                  <input 
                    type="datetime-local" 
                    style={{ width: '100%', padding: '10px', borderRadius: '6px', border: '1px solid #ccc', marginTop: '4px' }}
                    value={newScheduledAt} 
                    onChange={(e) => setNewScheduledAt(e.target.value)}
                  />
                </div>
                <button 
                  type="submit" 
                  className="pill-button"
                  style={{ marginTop: '10px', alignSelf: 'flex-start' }}
                >
                  Schedule Round
                </button>
              </form>
            </div>
          </div>
        </div>

      </div>
    </>
  );
}
