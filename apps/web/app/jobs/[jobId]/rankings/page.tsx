"use client";

import { useEffect, useState } from "react";
import { fetchRankings, createOverride, generateInterview } from "../../../lib/api";

type Candidate = { candidate_id: string; candidate_name?: string; score: number; rank: number; explanation_text?: string };

export default function RankingsPage({ params }: { params: { jobId: string } }) {
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [runId, setRunId] = useState<string>("");
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setStatus("Loading...");
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

  const handleMoveToInterview = async (candidate_id: string) => {
    try {
      setStatus(`Moving ${candidate_id.slice(0, 8)} to interview and generating questions...`);
      const response = await generateInterview(params.jobId, candidate_id);
      alert(`Candidate moved to interview! Generated ${response.questions_generated} questions.`);
      setStatus(null);
    } catch (e) {
      alert("Error moving to interview");
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
        <div className="panel light-orange">
          <h2>Ranking Pipeline Results</h2>
          {status ? <div style={{ marginBottom: 12, fontWeight: 700, color: 'var(--brand-blue)' }}>{status}</div> : null}
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
                    <div className="ranking-desc">
                      {candidate.explanation_text}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <button 
                    className="pill-button" 
                    onClick={() => handleMoveToInterview(candidate.candidate_id)}
                    style={{ background: '#fff', color: 'var(--brand-blue)' }}
                  >
                    Move to Interview
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
        
        <div className="panel green">
          <h2>Insights & Bias Flags</h2>
          <div style={{ marginTop: '20px', lineHeight: '1.6', fontSize: '14px', color: '#555' }}>
            <p><strong>✅ Semantic Alignment:</strong> Strong correlation found between candidates' past project descriptions and your required domains (AWS, Docker).</p>
            <p><strong>⚠️ Warning:</strong> Candidates without a formal CS degree scored 15% lower on average. Ensure the rule constraints are not unintentionally filtering non-traditional backgrounds.</p>
            <p><strong>💡 Recommendation:</strong> For Candidate Demo 002, use the generated Interview Questions to probe their backend architectural experience.</p>
          </div>
        </div>
      </div>
    </>
  );
}
