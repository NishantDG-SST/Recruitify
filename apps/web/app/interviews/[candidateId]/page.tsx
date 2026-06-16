"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  fetchCandidateRounds,
  scheduleInterviewRound,
  updateInterviewRound,
  generateInterview,
} from "../../lib/api";

export default function CandidateInterviewPage({
  params,
}: {
  params: { candidateId: string };
}) {
  const { candidateId } = params;

  const [candidate, setCandidate] = useState<any>(null);
  const [rounds, setRounds] = useState<any[]>([]);
  const [newRoundName, setNewRoundName] = useState("Technical Interview");
  const [newInterviewer, setNewInterviewer] = useState("");
  const [newScheduledAt, setNewScheduledAt] = useState("");
  const [feedbackRoundId, setFeedbackRoundId] = useState<string | null>(null);
  const [roundFeedback, setRoundFeedback] = useState("");
  const [roundStatus, setRoundStatus] = useState("passed");
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  // Derive jobId from the candidate's profile (same pattern as original profile page)
  const jobId = candidate?.profile?.job_id || "all";

  const loadRounds = async (jId: string) => {
    try {
      const data = await fetchCandidateRounds(jId, candidateId);
      setRounds(data || []);
    } catch (e) {
      console.error("Failed to load rounds", e);
    }
  };

  useEffect(() => {
    fetch(`/api/jobs/all/candidates/details/${candidateId}`)
      .then((res) => res.json())
      .then((data) => {
        setCandidate(data);
        const jId = data.profile?.job_id || "all";
        loadRounds(jId);
      })
      .catch(console.error);
  }, [candidateId]);

  const handleScheduleRound = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await scheduleInterviewRound(jobId, candidateId, {
        round_name: newRoundName,
        interviewer_name: newInterviewer || undefined,
        scheduled_at: newScheduledAt
          ? new Date(newScheduledAt).toISOString()
          : undefined,
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
    try {
      await updateInterviewRound(jobId, candidateId, roundId, {
        status: roundStatus,
        feedback: roundFeedback,
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
    setIsGenerating(true);
    setStatusMessage("Generating tailored interview questions...");
    try {
      const response = await fetch(
        `/api/jobs/${jobId}/candidates/details/${candidateId}/interviews`,
        { method: "POST" }
      );
      if (response.ok) {
        const result = await response.json();
        // Reload full candidate to get new questions
        const detailsRes = await fetch(
          `/api/jobs/${jobId}/candidates/details/${candidateId}`
        );
        if (detailsRes.ok) {
          const updated = await detailsRes.json();
          setCandidate(updated);
        }
        alert(`Successfully generated ${result.questions_generated} questions!`);
      } else {
        alert("Failed to generate questions");
      }
    } catch (e) {
      console.error(e);
      alert("Error generating questions");
    } finally {
      setIsGenerating(false);
      setStatusMessage(null);
    }
  };

  if (!candidate) {
    return <div style={{ padding: 40 }}>Loading interview data...</div>;
  }

  const questions: any[] = candidate.questions || [];

  return (
    <>
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "16px",
          marginBottom: "20px",
        }}
      >
        <Link href="/interviews">
          <button
            className="pill-button"
            style={{
              background: "var(--bg-page)",
              color: "var(--text-main)",
            }}
          >
            ← Interview Hub
          </button>
        </Link>
        <div>
          <h1 className="page-title" style={{ margin: 0 }}>
            {candidate.profile?.name || "Candidate"} — Interview
          </h1>
          <p
            className="page-subtitle"
            style={{ margin: "4px 0 0 0", fontSize: "13px" }}
          >
            AI-generated questions &amp; interview scheduling for this candidate.
          </p>
        </div>
      </div>

      <div className="content-grid">
        {/* AI Generated Interview Questions Panel */}
        <div
          className="panel light-orange"
          style={{ gridColumn: "1 / -1" }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
            }}
          >
            <h2>AI Generated Interview Questions</h2>
            <button
              className="pill-button"
              onClick={handleGenerateQuestions}
              disabled={isGenerating}
              style={{ fontSize: "12px" }}
            >
              {isGenerating ? "Generating..." : questions.length > 0 ? "Regenerate Questions" : "Generate Questions"}
            </button>
          </div>

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

          <div style={{ marginTop: "20px" }}>
            {statusMessage ? (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  padding: "40px 0",
                }}
              >
                <div className="loading-spinner"></div>
                <div style={{ fontWeight: 700, color: "#7209b7" }}>
                  {statusMessage}
                </div>
              </div>
            ) : questions.length > 0 ? (
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "16px",
                }}
              >
                {questions.map((q: any, i: number) => (
                  <div
                    key={i}
                    style={{
                      padding: "16px",
                      background: "#fff",
                      borderRadius: "8px",
                      border: "1px solid rgba(0,0,0,0.05)",
                      boxShadow: "0 2px 4px rgba(0,0,0,0.02)",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        marginBottom: "8px",
                      }}
                    >
                      <span
                        style={{
                          fontWeight: 800,
                          color: "#7209b7",
                          fontSize: "12px",
                        }}
                      >
                        Q{i + 1}
                      </span>
                      <span
                        style={{
                          fontWeight: 800,
                          color: "var(--text-muted)",
                          fontSize: "10px",
                          textTransform: "uppercase",
                        }}
                      >
                        {q.category?.replace("_", " ")} • Target:{" "}
                        {q.target_skill}
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: "15px",
                        fontWeight: 600,
                        marginBottom: "8px",
                        color: "#1b4332",
                      }}
                    >
                      {q.prompt}
                    </div>
                    <div style={{ fontSize: "13px", color: "#555" }}>
                      <strong>Rationale:</strong> {q.rationale}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  padding: "40px 0",
                  border: "2px dashed rgba(0,0,0,0.1)",
                  borderRadius: "12px",
                  background: "rgba(255,255,255,0.3)",
                }}
              >
                <p
                  style={{
                    color: "#555",
                    marginBottom: "16px",
                    fontWeight: 600,
                  }}
                >
                  No interview questions generated yet for this candidate.
                </p>
                <button
                  className="pill-button"
                  onClick={handleGenerateQuestions}
                  disabled={isGenerating}
                >
                  Generate Questions Now
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Schedule a New Round Panel */}
        <div className="panel green">
          <h2>Schedule a New Round</h2>
          <form
            onSubmit={handleScheduleRound}
            style={{
              marginTop: "20px",
              display: "flex",
              flexDirection: "column",
              gap: "14px",
            }}
          >
            <div>
              <label
                style={{ fontSize: "12px", fontWeight: 700, display: "block", marginBottom: "4px" }}
              >
                Round Type / Name
              </label>
              <select
                style={{
                  width: "100%",
                  padding: "10px",
                  borderRadius: "6px",
                  border: "1px solid #ccc",
                }}
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
              <label
                style={{ fontSize: "12px", fontWeight: 700, display: "block", marginBottom: "4px" }}
              >
                Interviewer Name
              </label>
              <input
                type="text"
                placeholder="e.g. John Doe"
                style={{
                  width: "100%",
                  padding: "10px",
                  borderRadius: "6px",
                  border: "1px solid #ccc",
                  boxSizing: "border-box",
                }}
                value={newInterviewer}
                onChange={(e) => setNewInterviewer(e.target.value)}
              />
            </div>
            <div>
              <label
                style={{ fontSize: "12px", fontWeight: 700, display: "block", marginBottom: "4px" }}
              >
                Scheduled Date &amp; Time
              </label>
              <input
                type="datetime-local"
                style={{
                  width: "100%",
                  padding: "10px",
                  borderRadius: "6px",
                  border: "1px solid #ccc",
                  boxSizing: "border-box",
                }}
                value={newScheduledAt}
                onChange={(e) => setNewScheduledAt(e.target.value)}
              />
            </div>
            <button
              type="submit"
              className="pill-button"
              style={{ alignSelf: "flex-start", marginTop: "4px" }}
            >
              Schedule Round
            </button>
          </form>
        </div>

        {/* Interview Round History Panel */}
        <div className="panel light-orange">
          <h2>Interview Round History</h2>
          <div style={{ marginTop: "16px" }}>
            {rounds.length === 0 ? (
              <p style={{ fontStyle: "italic", color: "#666" }}>
                No rounds scheduled yet for this candidate.
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {rounds.map((round) => (
                  <div
                    key={round.id}
                    style={{
                      background: "#fff",
                      border: "1px solid rgba(0,0,0,0.07)",
                      padding: "12px",
                      borderRadius: "8px",
                    }}
                  >
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                      }}
                    >
                      <strong style={{ color: "#1b4332" }}>
                        {round.round_name}
                      </strong>
                      <span
                        className="tag"
                        style={{
                          textTransform: "uppercase",
                          fontSize: "10px",
                        }}
                      >
                        {round.status}
                      </span>
                    </div>
                    <div
                      style={{ fontSize: "12px", color: "#666", marginTop: "4px" }}
                    >
                      Interviewer: {round.interviewer_name || "Unassigned"} |
                      Date:{" "}
                      {round.scheduled_at
                        ? new Date(round.scheduled_at).toLocaleString()
                        : "TBD"}
                    </div>
                    {round.feedback && (
                      <div
                        style={{
                          background: "#e9f5ed",
                          padding: "8px",
                          borderRadius: "4px",
                          marginTop: "8px",
                          fontSize: "12px",
                          color: "#333",
                        }}
                      >
                        <strong>Feedback:</strong> {round.feedback}
                      </div>
                    )}

                    {round.status === "scheduled" && (
                      <button
                        className="pill-button"
                        style={{
                          marginTop: "8px",
                          fontSize: "11px",
                          padding: "4px 10px",
                        }}
                        onClick={() => {
                          setFeedbackRoundId(round.id);
                          setRoundStatus("passed");
                        }}
                      >
                        Log Feedback / Result
                      </button>
                    )}

                    {feedbackRoundId === round.id && (
                      <div
                        style={{
                          marginTop: "12px",
                          borderTop: "1px solid #ccc",
                          paddingTop: "12px",
                        }}
                      >
                        <div style={{ marginBottom: "8px" }}>
                          <label
                            style={{ fontSize: "12px", fontWeight: 700 }}
                          >
                            Outcome Status:
                          </label>
                          <select
                            style={{
                              width: "100%",
                              padding: "6px",
                              borderRadius: "4px",
                              border: "1px solid #ccc",
                              marginTop: "4px",
                            }}
                            value={roundStatus}
                            onChange={(e) => setRoundStatus(e.target.value)}
                          >
                            <option value="passed">Passed</option>
                            <option value="failed">Failed</option>
                            <option value="completed">Completed (Other)</option>
                          </select>
                        </div>
                        <div style={{ marginBottom: "8px" }}>
                          <label
                            style={{ fontSize: "12px", fontWeight: 700 }}
                          >
                            Feedback / Notes:
                          </label>
                          <textarea
                            style={{
                              width: "100%",
                              padding: "6px",
                              borderRadius: "4px",
                              border: "1px solid #ccc",
                              marginTop: "4px",
                              fontSize: "12px",
                              boxSizing: "border-box",
                            }}
                            rows={3}
                            placeholder="Write interviewer notes..."
                            value={roundFeedback}
                            onChange={(e) => setRoundFeedback(e.target.value)}
                          />
                        </div>
                        <div style={{ display: "flex", gap: "8px" }}>
                          <button
                            className="pill-button"
                            onClick={() => handleUpdateRoundSubmit(round.id)}
                          >
                            Save Feedback
                          </button>
                          <button
                            className="pill-button"
                            style={{ background: "#eee", color: "#333" }}
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
        </div>
      </div>
    </>
  );
}
