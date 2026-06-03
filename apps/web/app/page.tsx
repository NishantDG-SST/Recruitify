"use client";

import { useState, useEffect } from "react";
import { fetchJobs, fetchCandidates } from "./lib/api";

export default function Home() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [candidates, setCandidates] = useState<any[]>([]);

  useEffect(() => {
    fetchJobs().then(d => setJobs(d.jobs || [])).catch(console.error);
    fetchCandidates("all").then(d => setCandidates(d.candidates || [])).catch(console.error);
  }, []);

  return (
    <>
      <h1 className="page-title">Dashboard Overview</h1>
      <p className="page-subtitle">Here's today's overview for Recruit IQ.</p>

      <div className="stats-grid">
        <div className="stat-card purple">
          <div className="stat-title">Active Jobs</div>
          <div className="stat-value">{jobs.length}</div>
          <div className="stat-trend">Live Requisitions</div>
        </div>
        <div className="stat-card orange">
          <div className="stat-title">Candidates Ranked</div>
          <div className="stat-value">{candidates.length}</div>
          <div className="stat-trend">Total in Pipeline</div>
        </div>
        <div className="stat-card pink">
          <div className="stat-title">Time to Hire (Avg)</div>
          <div className="stat-value">--</div>
          <div className="stat-trend">Gathering Data</div>
        </div>
      </div>

      <div className="content-grid">
        <div className="panel light-orange">
          <h2>Recent Activity</h2>
          <div className="ranking-list" style={{ marginTop: '20px' }}>
            {jobs.length === 0 && <p style={{ color: '#555' }}>No recent activity. Create a job to get started!</p>}
            {jobs.slice(0,4).map(job => (
              <div className="ranking-item" key={job.id}>
                <div className="ranking-info">
                  <div className="ranking-name">Created Job: {job.title}</div>
                  <div className="ranking-desc">{job.id.slice(0, 8)}</div>
                </div>
                <div className="tag">{new Date(job.created_at).toLocaleDateString()}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="panel green">
          <h2>Pipeline Health</h2>
          <div style={{ marginTop: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontWeight: '800' }}>
                <span>Resume Extraction Success</span>
                <span>{candidates.length > 0 ? '100%' : '--'}</span>
              </div>
              <div style={{ height: '12px', background: 'rgba(255,255,255,0.4)', borderRadius: '999px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: candidates.length > 0 ? '100%' : '0%', background: '#38120b', borderRadius: '999px' }}></div>
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontWeight: '800' }}>
                <span>Semantic Match Latency</span>
                <span>{candidates.length > 0 ? '45ms' : '--'}</span>
              </div>
              <div style={{ height: '12px', background: 'rgba(255,255,255,0.4)', borderRadius: '999px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: candidates.length > 0 ? '15%' : '0%', background: '#ff9b44', borderRadius: '999px' }}></div>
              </div>
            </div>
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px', fontWeight: '800' }}>
                <span>Bias Checks Passed</span>
                <span>{candidates.length > 0 ? '100%' : '--'}</span>
              </div>
              <div style={{ height: '12px', background: 'rgba(255,255,255,0.4)', borderRadius: '999px', overflow: 'hidden' }}>
                <div style={{ height: '100%', width: candidates.length > 0 ? '100%' : '0%', background: '#bde47e', borderRadius: '999px' }}></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
