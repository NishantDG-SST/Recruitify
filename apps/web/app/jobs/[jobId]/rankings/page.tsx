"use client";

import { useEffect, useState } from "react";
import { fetchRankings, createOverride, generateInterview, fetchBiasAnalysis, simulateRankings, updateCandidateStatus, scheduleInterviewRound } from "../../../lib/api";

type Candidate = { 
  candidate_id: string; 
  candidate_name?: string; 
  score: number; 
  rank: number; 
  explanation_text?: string;
  category_scores?: {
    hard_skills?: number;
    soft_skills?: number;
    experience?: number;
    domain_knowledge?: number;
  };
};

export default function RankingsPage({ params }: { params: { jobId: string } }) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [runId, setRunId] = useState<string>("");
  const [status, setStatus] = useState<string | null>(null);
  
  const [skillsWeight, setSkillsWeight] = useState(0.4);
  const [expWeight, setExpWeight] = useState(0.3);
  const [eduWeight, setEduWeight] = useState(0.2);
  const [semWeight, setSemWeight] = useState(0.1);

  const handleRecalculate = async () => {
    try {
      setStatus("Simulating ranking with custom weights...");
      const total = skillsWeight + expWeight + eduWeight + semWeight;
      if (total === 0) {
        alert("At least one weight must be greater than 0");
        setStatus(null);
        return;
      }
      // Normalize weights so they sum to 1.0
      const normalizedWeights = {
        skills: skillsWeight / total,
        experience: expWeight / total,
        education: eduWeight / total,
        semantic_similarity: semWeight / total
      };

      const response = await simulateRankings(params.jobId, normalizedWeights);
      setCandidates(response.candidates || []);
      setRunId(response.run_id);
      setStatus(null);
      alert("Rankings recalculated successfully!");
    } catch (e) {
      console.error(e);
      alert("Error simulating rankings");
      setStatus(null);
    }
  };

  const [biasData, setBiasData] = useState<{
    metrics: Record<string, number>;
    flags: Array<{ flag_type: string; severity: string; message: string }>;
    hidden_gems: Array<{ snapshot_id: string; name: string }>;
  } | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setStatus("Loading...");
        // Check for URL query params for initial simulation
        if (typeof window !== "undefined") {
          const urlParams = new URLSearchParams(window.location.search);
          const s = urlParams.get("skills");
          const ex = urlParams.get("experience");
          const ed = urlParams.get("education");
          const sem = urlParams.get("semantic");

          if (s !== null || ex !== null || ed !== null || sem !== null) {
            const wSkills = s !== null ? parseFloat(s) : 0.4;
            const wExp = ex !== null ? parseFloat(ex) : 0.3;
            const wEdu = ed !== null ? parseFloat(ed) : 0.2;
            const wSem = sem !== null ? parseFloat(sem) : 0.1;

            setSkillsWeight(wSkills);
            setExpWeight(wExp);
            setEduWeight(wEdu);
            setSemWeight(wSem);

            const total = wSkills + wExp + wEdu + wSem;
            if (total > 0) {
              const normalizedWeights = {
                skills: wSkills / total,
                experience: wExp / total,
                education: wEdu / total,
                semantic_similarity: wSem / total
              };
              const response = await simulateRankings(params.jobId, normalizedWeights);
              setCandidates(response.candidates || []);
              setRunId(response.run_id);
              setStatus(null);
              return;
            }
          }
        }

        const response = await fetchRankings(params.jobId);
        setCandidates(response.candidates || []);
        setRunId(response.run_id);
        setStatus(null);
      } catch (error) {
        setStatus("Failed to load rankings");
      }
    };
    load();
  }, [params.jobId]);

  useEffect(() => {
    if (!runId) return;
    const loadBias = async () => {
      try {
        const response = await fetchBiasAnalysis(params.jobId, runId);
        setBiasData(response);
      } catch (error) {
        console.error("Failed to load bias analysis", error);
      }
    };
    loadBias();
  }, [params.jobId, runId]);

  const handleOverride = async (candidate_id: string, old_rank: number) => {
    const newRankStr = prompt("Enter new rank for candidate:");
    if (!newRankStr) return;
    const newRank = parseInt(newRankStr);
    const reason = prompt("Reason for override:");
    if (!reason) return;

    try {
      await createOverride(params.jobId, runId, {
        candidate_id,
        old_rank,
        new_rank: newRank,
        reason
      });
      alert("Override saved successfully!");
    } catch (e) {
      alert("Error saving override");
    }
  };

  const [movedCandidates, setMovedCandidates] = useState<Record<string, boolean>>({});

  const handleMoveToInterview = async (candidate_id: string) => {
    try {
      setStatus(`Moving candidate to interview stage...`);
      await updateCandidateStatus(params.jobId, candidate_id, "interviewing");
      
      setStatus(`Scheduling screening round...`);
      await scheduleInterviewRound(params.jobId, candidate_id, {
        round_name: "Screening",
        interviewer_name: "TBD",
        scheduled_at: new Date().toISOString()
      });
      
      setStatus(`Generating tailored questions...`);
      await generateInterview(params.jobId, candidate_id);
      
      setMovedCandidates(prev => ({ ...prev, [candidate_id]: true }));
      alert("Candidate moved to interview stage");
      setStatus(null);
    } catch (e) {
      console.error(e);
      alert("Error moving candidate to interview");
      setStatus(null);
    }
  };

  return (
    <>
      <h1 className="page-title">Rankings Overview</h1>
      <p className="page-subtitle">Here are the AI-matched candidates for {params.jobId}</p>

      <div className="stats-grid">
        <div className="stat-card purple">
          <div className="stat-title">Candidates Processed</div>
          <div className="stat-value">{candidates.length > 0 ? candidates.length : '...'}</div>
          <div className="stat-trend">↑ 12% vs last run</div>
        </div>
        <div className="stat-card orange">
          <div className="stat-title">Avg. Match Score</div>
          <div className="stat-value">{candidates.length > 0 ? (candidates.reduce((a, b) => a + b.score, 0) / candidates.length).toFixed(1) : '...'}</div>
          <div className="stat-trend">Top 10% quality</div>
        </div>
        <div className="stat-card pink">
          <div className="stat-title">Must-Haves Met</div>
          <div className="stat-value">94%</div>
          <div className="stat-trend">High alignment</div>
        </div>
      </div>

      <div className="content-grid">
        {/* Left Column Stack */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* AI Weight Calibration (Simulation) Panel */}
          <div className="panel light-orange">
            <h2>AI Weight Calibration</h2>
            <p style={{ fontSize: '13px', color: 'var(--text-muted)', marginBottom: '20px' }}>
              Adjust the slider weights to tune the scoring model. Ranks and scores will recalculate in real-time.
            </p>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '20px' }}>
              {[
                { label: "Skills Weight", value: skillsWeight, setter: setSkillsWeight, desc: "Importance of skill matches" },
                { label: "Experience Weight", value: expWeight, setter: setExpWeight, desc: "Importance of candidate experience" },
                { label: "Education Weight", value: eduWeight, setter: setEduWeight, desc: "Importance of educational credentials" },
                { label: "Semantic Weight", value: semWeight, setter: setSemWeight, desc: "Importance of semantic CV-to-JD match" },
              ].map((slider, idx) => (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '8px', background: '#fff', padding: '14px', borderRadius: '12px', border: '1px solid rgba(0,0,0,0.05)' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontWeight: 800, fontSize: '12px' }}>
                    <span>{slider.label}</span>
                    <span style={{ color: '#b4462f' }}>{(slider.value * 100).toFixed(0)}%</span>
                  </div>
                  <input 
                    type="range" 
                    min="0" 
                    max="1" 
                    step="0.05" 
                    value={slider.value} 
                    onChange={(e) => slider.setter(parseFloat(e.target.value))}
                    style={{ width: '100%', accentColor: '#b4462f', cursor: 'pointer' }}
                  />
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', fontStyle: 'italic' }}>{slider.desc}</span>
                </div>
              ))}
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <span style={{ fontSize: '12px', fontWeight: 700, color: 'var(--text-muted)' }}>
                Sum of raw weights: <strong style={{ color: Math.abs(skillsWeight + expWeight + eduWeight + semWeight - 1.0) < 0.01 ? '#2d6a4f' : '#b4462f' }}>{(skillsWeight + expWeight + eduWeight + semWeight).toFixed(2)}</strong> (will auto-normalize to 1.0)
              </span>
              <button 
                className="pill-button" 
                onClick={handleRecalculate}
                style={{ background: '#b4462f', color: '#fff', padding: '10px 24px', fontSize: '13px', fontWeight: 800 }}
              >
                Re-calculate Rankings
              </button>
            </div>
          </div>

          {/* Ranking Pipeline Results */}
          <div className="panel light-orange">
            <h2>Ranking Pipeline Results</h2>
            {status ? <div style={{ marginBottom: 12, fontWeight: 700, color: '#b4462f' }}>{status}</div> : null}
            <div className="ranking-list">
              {candidates.map((candidate) => (
                <div className="ranking-item" key={candidate.candidate_id}>
                  <div className="ranking-avatar"></div>
                  <div className="ranking-info">
                    <div className="ranking-name">{candidate.candidate_name || candidate.candidate_id} <span className="tag" style={{ marginLeft: 8 }}>Rank #{candidate.rank}</span></div>
                    <div style={{ fontSize: '13px', fontWeight: 700, marginBottom: 4, color: '#b4462f' }}>
                      Score: {candidate.score.toFixed(1)}
                    </div>
                    {candidate.explanation_text && (
                      <div className="ranking-desc" style={{ marginBottom: 12 }}>
                        {candidate.explanation_text}
                      </div>
                    )}
                    
                    {/* Score Breakdown Progress Bars */}
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', maxWidth: '450px', marginTop: '12px', background: 'rgba(255,255,255,0.4)', padding: '10px', borderRadius: '6px', border: '1px solid rgba(0,0,0,0.03)' }}>
                      {[
                        { label: "Hard Skills", value: candidate.category_scores?.hard_skills },
                        { label: "Soft Skills", value: candidate.category_scores?.soft_skills },
                        { label: "Experience", value: candidate.category_scores?.experience },
                        { label: "Domain Knowledge", value: candidate.category_scores?.domain_knowledge },
                      ].map((bar, idx) => (
                        <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                            <span>{bar.label}</span>
                            <span>{typeof bar.value === 'number' ? `${bar.value.toFixed(0)}%` : '0%'}</span>
                          </div>
                          <div style={{ width: '100%', height: '6px', background: 'rgba(0,0,0,0.06)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div style={{ 
                              width: `${bar.value || 0}%`, 
                              height: '100%', 
                              background: bar.label === 'Hard Skills' ? '#4361ee' : 
                                          bar.label === 'Soft Skills' ? '#4cc9f0' : 
                                          bar.label === 'Experience' ? '#f72585' : '#7209b7',
                              borderRadius: '3px',
                              transition: 'width 0.3s ease'
                            }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <button 
                      className="pill-button" 
                      onClick={() => handleMoveToInterview(candidate.candidate_id)}
                      disabled={movedCandidates[candidate.candidate_id]}
                      style={{ 
                        background: movedCandidates[candidate.candidate_id] ? '#e2e8f0' : '#fff', 
                        color: movedCandidates[candidate.candidate_id] ? '#64748b' : 'var(--brand-blue)',
                        cursor: movedCandidates[candidate.candidate_id] ? 'not-allowed' : 'pointer'
                      }}
                    >
                      {movedCandidates[candidate.candidate_id] ? "✓ In Interview" : "Move to Interview"}
                    </button>
                    <button 
                      className="pill-button" 
                      onClick={() => handleOverride(candidate.candidate_id, candidate.rank)}
                    >
                      Override
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
        
        <div className="panel green">
          <h2>Diversity & Bias Audit</h2>
          {biasData ? (
            <div style={{ marginTop: '20px', fontSize: '14px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
              
              {/* Score Distribution Metrics */}
              <div>
                <h3 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#1b4332' }}>Score Distribution</h3>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
                  <div style={{ background: '#e9f5ed', padding: '10px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '11px', color: '#555' }}>Mean Score</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: '#1b4332' }}>
                      {biasData.metrics?.mean?.toFixed(1) || 'N/A'}
                    </div>
                  </div>
                  <div style={{ background: '#e9f5ed', padding: '10px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '11px', color: '#555' }}>Std. Deviation</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: '#1b4332' }}>
                      {biasData.metrics?.std_dev?.toFixed(1) || 'N/A'}
                    </div>
                  </div>
                  <div style={{ background: '#e9f5ed', padding: '10px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '11px', color: '#555' }}>Minimum Score</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: '#1b4332' }}>
                      {biasData.metrics?.min?.toFixed(1) || 'N/A'}
                    </div>
                  </div>
                  <div style={{ background: '#e9f5ed', padding: '10px', borderRadius: '6px' }}>
                    <div style={{ fontSize: '11px', color: '#555' }}>Maximum Score</div>
                    <div style={{ fontSize: '18px', fontWeight: 700, color: '#1b4332' }}>
                      {biasData.metrics?.max?.toFixed(1) || 'N/A'}
                    </div>
                  </div>
                </div>
              </div>

              {/* Homogeneity Alerts & Flags */}
              <div>
                <h3 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#1b4332' }}>Homogeneity & Bias Warnings</h3>
                {biasData.flags && biasData.flags.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {biasData.flags.map((flag, idx) => (
                      <div 
                        key={idx} 
                        style={{ 
                          borderLeft: flag.severity === 'critical' ? '4px solid #d90429' : '4px solid #f77f00',
                          background: flag.severity === 'critical' ? '#ffebee' : '#fff3cd', 
                          padding: '10px', 
                          borderRadius: '4px',
                          color: '#333'
                        }}
                      >
                        <strong style={{ textTransform: 'uppercase', fontSize: '10px', color: '#666' }}>
                          {flag.severity} - {flag.flag_type.replace('_', ' ')}
                        </strong>
                        <div style={{ fontSize: '12px', marginTop: '4px' }}>{flag.message}</div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: '#2d6a4f', fontSize: '13px', fontStyle: 'italic' }}>
                    ✅ No homogeneity risks or low score variance detected.
                  </div>
                )}
              </div>

              {/* Hidden Gems Section */}
              <div>
                <h3 style={{ fontSize: '14px', fontWeight: 700, marginBottom: '8px', color: '#1b4332' }}>
                  💡 Hidden Gems (Non-Traditional Education)
                </h3>
                {biasData.hidden_gems && biasData.hidden_gems.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {biasData.hidden_gems.map((gem, idx) => (
                      <div 
                        key={idx} 
                        style={{ 
                          background: '#fff', 
                          border: '1px solid #c7f9cc', 
                          padding: '10px', 
                          borderRadius: '6px',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <div>
                          <strong style={{ color: '#1b4332' }}>{gem.name}</strong>
                          <div style={{ fontSize: '11px', color: '#666' }}>Alternative Education Pathway</div>
                        </div>
                        <span style={{ fontSize: '10px', background: '#d8f3dc', color: '#1b4332', padding: '3px 8px', borderRadius: '12px', fontWeight: 700 }}>
                          High Potential
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ color: '#555', fontSize: '13px', fontStyle: 'italic' }}>
                    No non-traditional background candidates meet the gem criteria (score &ge; 60.0) in this batch.
                  </div>
                )}
              </div>

            </div>
          ) : (
            <div style={{ marginTop: '20px', fontStyle: 'italic', color: '#888' }}>
              Calculating bias metrics for run {runId || '...'}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
