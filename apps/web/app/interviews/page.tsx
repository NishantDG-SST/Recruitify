"use client";

import { useEffect, useState } from "react";
import { fetchInterviews, fetchJobs } from "../lib/api";
import Link from "next/link";

export default function InterviewsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [interviews, setInterviews] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");

  useEffect(() => {
    fetchJobs()
      .then((data) => {
        setJobs(data.jobs || []);
        if (data.jobs && data.jobs.length > 0) {
          setSelectedJob(data.jobs[0].id);
        }
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedJob) {
      loadInterviews(selectedJob);
    }
  }, [selectedJob]);

  const loadInterviews = async (jobId: string) => {
    setIsLoading(true);
    try {
      const data = await fetchInterviews(jobId);
      setInterviews(data.interviews || []);
    } catch (e) {
      console.error("Failed to load interviews", e);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredInterviews = interviews.filter((item) => {
    if (statusFilter === "all") return true;
    return item.status === statusFilter;
  });

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>Interview Hub</h1>
          <p className="page-subtitle" style={{ margin: '4px 0 0 0' }}>Auto-generated questions and interview schedules.</p>
        </div>
        <select 
          className="search-bar" 
          style={{ padding: '10px 16px', borderRadius: '24px', border: '1px solid #ccc' }}
          value={selectedJob} 
          onChange={(e) => setSelectedJob(e.target.value)}
        >
          <option value="" disabled>Select Job</option>
          {jobs.map((job) => (
            <option key={job.id} value={job.id}>{job.title}</option>
          ))}
        </select>
      </div>

      {/* Filter Tabs */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '20px' }}>
        {["all", "scheduled", "passed", "failed", "completed"].map((tab) => (
          <button
            key={tab}
            className="pill-button"
            style={{
              background: statusFilter === tab ? '#1b4332' : 'var(--bg-page)',
              color: statusFilter === tab ? '#fff' : 'var(--text-main)',
              textTransform: 'uppercase',
              fontSize: '11px',
              padding: '6px 14px'
            }}
            onClick={() => setStatusFilter(tab)}
          >
            {tab}
          </button>
        ))}
      </div>

      <div className="content-grid">
        {/* Scheduled Interviews List */}
        <div className="panel light-orange">
          <h2>Upcoming & Past Interview Rounds</h2>
          <div className="ranking-list" style={{ marginTop: '20px' }}>
            {isLoading && <p>Loading interviews...</p>}
            {!isLoading && filteredInterviews.length === 0 && (
              <p style={{ color: '#555', fontSize: '14px' }}>
                No interviews match the filter criteria. Move candidates to the interview stage or schedule rounds to see them here.
              </p>
            )}
            {!isLoading && filteredInterviews.map((item) => (
              <div className="ranking-item" key={item.id}>
                <div className="ranking-avatar"></div>
                <div className="ranking-info">
                  <div className="ranking-name">
                    {item.candidate_name} 
                    <span className="tag" style={{ marginLeft: 8, background: '#ffd0b5' }}>{item.round_name}</span>
                  </div>
                  <div className="ranking-desc" style={{ fontSize: '12px', marginTop: '4px' }}>
                    Scheduled: {item.scheduled_at ? new Date(item.scheduled_at).toLocaleString() : "TBD"} | Interviewer: {item.interviewer_name || "TBD"}
                  </div>
                  {item.feedback && (
                    <div style={{ fontSize: '11px', color: '#555', marginTop: '6px', fontStyle: 'italic', background: 'rgba(0,0,0,0.02)', padding: '6px', borderRadius: '4px' }}>
                      <strong>Feedback:</strong> {item.feedback}
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span className="tag" style={{ textTransform: 'uppercase', fontSize: '10px' }}>{item.status}</span>
                  <Link href={`/candidates/${item.candidate_id}`}>
                    <button className="pill-button" style={{ fontSize: '11px', background: '#fff', color: '#1b4332' }}>
                      View Profile
                    </button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Tailored Question Banks Panel */}
        <div className="panel green">
          <h2>Tailored AI Question Banks</h2>
          <p style={{ fontSize: '14px', color: '#555', marginBottom: '20px' }}>
            Custom questions created using candidate profile gap verification.
          </p>
          
          <div className="ranking-list">
            {isLoading && <p>Loading question banks...</p>}
            {!isLoading && interviews.length === 0 && (
              <p style={{ color: '#555', fontSize: '14px' }}>
                No candidates have questions generated yet. Go to a Job's candidate rankings to generate custom questions.
              </p>
            )}
            {!isLoading && Array.from(new Set(interviews.map(i => i.candidate_id))).map((candId) => {
              const item = interviews.find(i => i.candidate_id === candId);
              return (
                <div className="ranking-item" key={candId}>
                  <div className="ranking-avatar" style={{ background: '#d8f3dc' }}></div>
                  <div className="ranking-info">
                    <div className="ranking-name" style={{ color: '#1b4332', fontWeight: 700 }}>{item?.candidate_name}</div>
                    <div className="ranking-desc" style={{ fontSize: '12px' }}>Resume Analysis & Tailored Questions Bank</div>
                  </div>
                  <Link href={`/interviews/${candId}`}>
                    <button className="pill-button" style={{ fontSize: '11px' }}>
                      View Questions
                    </button>
                  </Link>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
