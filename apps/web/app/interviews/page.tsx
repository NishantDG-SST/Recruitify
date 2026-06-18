"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchInterviewCandidates, fetchJobs, generateInterview, updateCandidateStatus } from "../lib/api";

type Question = { prompt: string; category?: string; rationale?: string; target_skill?: string };
type Candidate = { candidate_id: string; name: string; role: string; status: string; questions: Question[] };

const TABS = [
  { key: "scheduled", label: "Scheduled", statuses: ["interview", "interviewing"], color: "#7209b7", cardBg: "var(--card-purple)", icon: "🎙️" },
  { key: "selected", label: "Selected", statuses: ["selected"], color: "#2d6a4f", cardBg: "var(--card-green)", icon: "✅" },
  { key: "rejected", label: "Rejected", statuses: ["rejected"], color: "#d90429", cardBg: "linear-gradient(135deg, #ffc2c9, #ffe0e3)", icon: "❌" },
];

export default function InterviewsPage() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [selectedJob, setSelectedJob] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("scheduled");
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  useEffect(() => {
    fetchJobs()
      .then((data) => {
        setJobs(data.jobs || []);
        if (data.jobs && data.jobs.length > 0) setSelectedJob(data.jobs[0].id);
      })
      .catch(console.error);
  }, []);

  useEffect(() => {
    if (selectedJob) loadCandidates(selectedJob);
  }, [selectedJob]);

  const loadCandidates = async (jobId: string) => {
    setIsLoading(true);
    try {
      const data = await fetchInterviewCandidates(jobId);
      setCandidates(data.candidates || []);
    } catch (e) {
      console.error("Failed to load interview candidates", e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStartInterview = async (candidateId: string) => {
    setGeneratingId(candidateId);
    try {
      const result = await generateInterview(selectedJob, candidateId);
      setCandidates((prev) =>
        prev.map((c) => (c.candidate_id === candidateId ? { ...c, questions: result.questions || [] } : c))
      );
      setExpandedId(candidateId);
    } catch (e) {
      alert("Failed to generate interview questions.");
    } finally {
      setGeneratingId(null);
    }
  };

  const handleDecision = async (candidateId: string, status: string) => {
    setBusyId(candidateId);
    try {
      await updateCandidateStatus(selectedJob, candidateId, status);
      setCandidates((prev) =>
        prev.map((c) => (c.candidate_id === candidateId ? { ...c, status } : c))
      );
    } catch (e) {
      alert("Failed to update candidate status.");
    } finally {
      setBusyId(null);
    }
  };

  const tabFor = (status: string) => TABS.find((t) => t.statuses.includes(status)) || TABS[0];
  const countFor = (tabKey: string) =>
    candidates.filter((c) => TABS.find((t) => t.key === tabKey)!.statuses.includes(c.status)).length;
  const visible = candidates.filter((c) => tabFor(c.status).key === activeTab);

  const initials = (name: string) => name.split(" ").map((n) => n[0]).join("").toUpperCase().slice(0, 2);

  const renderQuestions = (c: Candidate) => (
    <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
      {c.questions.map((q, i) => (
        <div key={i} style={{ padding: 14, background: "#fff", borderRadius: 14, border: "1px solid rgba(0,0,0,0.05)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span style={{ fontWeight: 900, color: "#7209b7", fontSize: 12 }}>Q{i + 1}</span>
            <span style={{ fontWeight: 800, color: "var(--text-muted)", fontSize: 10, textTransform: "uppercase" }}>
              {(q.category || "general").replace("_", " ")} · {q.target_skill}
            </span>
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 6, color: "#38120b" }}>{q.prompt}</div>
          {q.rationale && <div style={{ fontSize: 12, color: "#6b5a52" }}><strong>Rationale:</strong> {q.rationale}</div>}
        </div>
      ))}
    </div>
  );

  return (
    <>
      <style>{`
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .spinner-sm { border: 3px solid rgba(0,0,0,0.1); width: 18px; height: 18px; border-radius: 50%; border-left-color: #7209b7; animation: spin 0.9s linear infinite; display: inline-block; }
      `}</style>

      <div style={{ marginBottom: 20 }}>
        <h1 className="page-title" style={{ margin: 0 }}>Interview Hub 🎙️</h1>
        <p className="page-subtitle" style={{ margin: "4px 0 0 0" }}>Run interviews and decide who moves forward.</p>
      </div>

      {/* Job switcher */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ fontWeight: 900, fontSize: 11, letterSpacing: 1, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 10 }}>
          Jobs
        </div>
        {jobs.length === 0 ? (
          <div className="ranking-item" style={{ maxWidth: 320 }}>
            <div className="ranking-info"><div className="ranking-desc">No jobs yet. Create a job to begin.</div></div>
          </div>
        ) : (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
            {jobs.map((job) => {
              const active = selectedJob === job.id;
              return (
                <button
                  key={job.id}
                  onClick={() => { setSelectedJob(job.id); setExpandedId(null); }}
                  style={{
                    textAlign: "left", cursor: "pointer", minWidth: 200,
                    border: "none", borderLeft: `6px solid ${active ? "#ff7d29" : "transparent"}`,
                    borderRadius: 16, padding: "14px 18px",
                    background: active ? "var(--card-light-orange)" : "rgba(56,18,11,0.05)",
                    boxShadow: active ? "0 6px 16px rgba(255,123,41,0.25)" : "none",
                    transition: "all 0.2s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 16 }}>💼</span>
                    <span style={{ fontWeight: 800, fontSize: 15, color: "var(--text-main)" }}>{job.title}</span>
                  </div>
                  <div style={{ fontSize: 11, color: "var(--text-muted)", fontWeight: 700, marginTop: 4 }}>
                    {job.created_at ? `Created ${new Date(job.created_at).toLocaleDateString()}` : ""}
                    {active ? "  ·  ● Active" : ""}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Pipeline summary cards (also the stage filter) */}
      <div className="stats-grid" style={{ marginBottom: 24 }}>
        {TABS.map((tab) => {
          const active = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              className="stat-card"
              onClick={() => { setActiveTab(tab.key); setExpandedId(null); }}
              style={{
                background: tab.cardBg, cursor: "pointer", border: "none", textAlign: "left",
                outline: active ? `3px solid ${tab.color}` : "3px solid transparent",
                outlineOffset: 2, transform: active ? "translateY(-4px)" : "none",
              }}
            >
              <div className="stat-title"><span style={{ fontSize: 18 }}>{tab.icon}</span> {tab.label}</div>
              <div className="stat-value">{countFor(tab.key)}</div>
              <div className="stat-trend">{active ? "Viewing" : "View stage"}</div>
            </button>
          );
        })}
      </div>

      {/* Board */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {isLoading && (
          <div className="panel light-orange" style={{ textAlign: "center", padding: 40 }}>
            <span className="spinner-sm" style={{ borderLeftColor: "#b4462f" }} />
            <p style={{ color: "#6b5a52", fontWeight: 700, marginTop: 12 }}>Loading candidates...</p>
          </div>
        )}

        {!isLoading && !selectedJob && (
          <div style={{ textAlign: "center", padding: "48px 24px", border: "2px dashed rgba(56,18,11,0.18)", borderRadius: 20, background: "rgba(255,255,255,0.4)" }}>
            <div style={{ fontSize: 44 }}>📭</div>
            <p style={{ color: "#6b5a52", fontWeight: 800, fontSize: 16, margin: "10px 0 0" }}>Pick a job above</p>
            <p style={{ color: "#8a7a72", margin: "4px 0 0" }}>Select a job to view its interview pipeline.</p>
          </div>
        )}

        {!isLoading && selectedJob && visible.length === 0 && (
          <div style={{ textAlign: "center", padding: "48px 24px", border: "2px dashed rgba(56,18,11,0.18)", borderRadius: 20, background: "rgba(255,255,255,0.4)" }}>
            <div style={{ fontSize: 44 }}>📭</div>
            <p style={{ color: "#6b5a52", fontWeight: 800, fontSize: 16, margin: "10px 0 0" }}>
              {activeTab === "scheduled" ? "No candidates scheduled yet" : `No ${activeTab} candidates yet`}
            </p>
            <p style={{ color: "#8a7a72", margin: "4px 0 0" }}>
              {activeTab === "scheduled"
                ? "Move candidates to the interview stage from their profile or the rankings page →"
                : `Candidates you ${activeTab === "selected" ? "select" : "reject"} after an interview will appear here.`}
            </p>
          </div>
        )}

        {!isLoading && visible.map((c) => {
          const isScheduled = activeTab === "scheduled";
          const hasQuestions = (c.questions || []).length > 0;
          const expanded = expandedId === c.candidate_id;
          const generating = generatingId === c.candidate_id;
          const busy = busyId === c.candidate_id;
          const accent = tabFor(c.status).color;

          return (
            <div key={c.candidate_id} className="panel" style={{ borderLeft: `6px solid ${accent}` }}>
              <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
                <div style={{
                  width: 52, height: 52, borderRadius: "50%", background: "var(--card-orange)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontWeight: 900, color: "#fff", fontSize: 18, flexShrink: 0,
                }}>{initials(c.name)}</div>

                <div style={{ flex: 1, minWidth: 180 }}>
                  <div style={{ fontWeight: 800, fontSize: 17 }}>{c.name}</div>
                  <div style={{ fontSize: 13, color: "var(--text-muted)", fontWeight: 600 }}>{c.role}</div>
                </div>

                <span className="tag" style={{ textTransform: "uppercase", fontSize: 10, fontWeight: 800, background: `${accent}1a`, color: accent }}>
                  {c.status}
                </span>

                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <Link href={`/candidates/${c.candidate_id}`}>
                    <button className="pill-button" style={{ background: "#fff", color: "#1b4332", border: "1px solid #ddd" }}>View Profile</button>
                  </Link>

                  {isScheduled && !hasQuestions && (
                    <button className="pill-button" style={{ background: "#7209b7", color: "#fff", padding: "8px 18px" }}
                      onClick={() => handleStartInterview(c.candidate_id)} disabled={generating}>
                      {generating ? <span className="spinner-sm" /> : "▶ Start Interview"}
                    </button>
                  )}

                  {hasQuestions && (
                    <button className="pill-button" style={{ background: "var(--bg-page)", color: "var(--text-main)" }}
                      onClick={() => setExpandedId(expanded ? null : c.candidate_id)}>
                      {expanded ? "Hide Questions" : `View Questions (${c.questions.length})`}
                    </button>
                  )}

                  {isScheduled && hasQuestions && (
                    <>
                      <button className="pill-button" style={{ background: "#2d6a4f", color: "#fff" }}
                        onClick={() => handleDecision(c.candidate_id, "selected")} disabled={busy}>✓ Select</button>
                      <button className="pill-button" style={{ background: "#d90429", color: "#fff" }}
                        onClick={() => handleDecision(c.candidate_id, "rejected")} disabled={busy}>✕ Reject</button>
                    </>
                  )}

                  {!isScheduled && (
                    <button className="pill-button" style={{ background: "var(--bg-page)", color: "var(--text-main)" }}
                      onClick={() => handleDecision(c.candidate_id, "interview")} disabled={busy}>↩ Back to Scheduled</button>
                  )}
                </div>
              </div>

              {generating && (
                <div style={{ marginTop: 12, fontSize: 13, color: "#7209b7", fontWeight: 800 }}>
                  Generating tailored questions from the CV &amp; job description...
                </div>
              )}

              {expanded && hasQuestions && renderQuestions(c)}
            </div>
          );
        })}
      </div>
    </>
  );
}
