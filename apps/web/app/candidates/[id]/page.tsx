"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function CandidateProfilePage({ params }: { params: { id: string } }) {
  const [candidate, setCandidate] = useState<any>(null);

  useEffect(() => {
    fetch(`/api/jobs/all/candidates/details/${params.id}`)
      .then(res => res.json())
      .then(data => setCandidate(data))
      .catch(console.error);
  }, [params.id]);

  if (!candidate) return <div style={{ padding: 40 }}>Loading profile...</div>;

  const p = candidate.profile || {};
  const name: string = p.name || "Candidate";
  const role: string = p.current_role || "Pipeline Candidate";
  const scores = candidate.scores || {};
  const status: string = candidate.status || "active";
  const initials = name.split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2);
  const skillTags = [...(p.skills || []), ...(p.soft_skills || []), ...(p.domains || [])];

  const hard = Math.round(scores.hard_skills || 0);
  const soft = Math.round(scores.soft_skills || 0);
  const exp = Math.round(scores.experience || 0);
  const domain = Math.round(scores.domain_knowledge || 0);
  const overall = Math.round((hard + soft + exp + domain) / 4);

  // Donut geometry for the overall match ring
  const R = 64;
  const C = 2 * Math.PI * R;

  const STATUS_STYLES: Record<string, { bg: string; color: string }> = {
    selected: { bg: "#d8f3dc", color: "#1b4332" },
    rejected: { bg: "#fde2e4", color: "#721c24" },
    interviewing: { bg: "#e7d3ff", color: "#5a189a" },
    interview: { bg: "#e7d3ff", color: "#5a189a" },
    extracted: { bg: "#ffe8d6", color: "#b4462f" },
  };
  const statusStyle = STATUS_STYLES[status] || { bg: "#ffe8d6", color: "#b4462f" };

  const IconBadge = ({ children, bg = "rgba(56,18,11,0.85)" }: { children: any; bg?: string }) => (
    <span style={{ width: 38, height: 38, borderRadius: "50%", background: bg, color: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>
      {children}
    </span>
  );

  return (
    <>
      {/* Hero header */}
      <div style={{ display: "flex", alignItems: "center", gap: 18, marginBottom: 8 }}>
        <Link href="/candidates">
          <button className="pill-button" style={{ background: "var(--bg-page)", color: "var(--text-main)" }}>← Back</button>
        </Link>
        <div style={{
          width: 64, height: 64, borderRadius: "50%", background: "var(--card-orange)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontWeight: 900, fontSize: 24, color: "#fff", boxShadow: "0 8px 16px rgba(255,123,41,0.35)"
        }}>{initials}</div>
        <div>
          <h1 className="page-title" style={{ margin: 0, fontSize: 38 }}>{name}</h1>
          <p style={{ margin: "4px 0 0", fontWeight: 700, color: "var(--text-muted)", fontSize: 16 }}>
            {role} · <span style={{ textTransform: "uppercase", color: statusStyle.color }}>{status}</span>
          </p>
        </div>
      </div>
      <p className="page-subtitle" style={{ marginBottom: 24 }}>Here's the full intelligence overview for {name.split(" ")[0]}.</p>

      {/* Stat cards */}
      <div className="stats-grid" style={{ marginBottom: 24 }}>
        <div className="stat-card purple">
          <div className="stat-title"><IconBadge>🧩</IconBadge> Hard Skills Match</div>
          <div className="stat-value">{hard}%</div>
          <div className="stat-trend">Technical alignment</div>
        </div>
        <div className="stat-card orange">
          <div className="stat-title"><IconBadge bg="rgba(255,255,255,0.25)">💼</IconBadge> Experience</div>
          <div className="stat-value">{p.years_experience ?? 0}<span style={{ fontSize: 22, fontWeight: 800 }}> yrs</span></div>
          <div className="stat-trend">{(p.career_trajectory || "—").toString().replace("_", " ")}</div>
        </div>
        <div className="stat-card pink">
          <div className="stat-title"><IconBadge>🏅</IconBadge> Domain Knowledge</div>
          <div className="stat-value">{domain}%</div>
          <div className="stat-trend">{(p.domains || []).length} domain(s)</div>
        </div>
      </div>

      {/* AI Summary */}
      <div className="panel light-orange" style={{ marginBottom: 24 }}>
        <h2>✨ AI Candidate Summary</h2>
        {p.cv_summary ? (
          <p style={{ marginTop: 4, fontSize: 16, lineHeight: 1.75 }}>{p.cv_summary}</p>
        ) : (
          <p style={{ marginTop: 4, color: "#6b5a52", fontStyle: "italic" }}>
            {status === "processing" ? "Summary will appear once the resume finishes processing." : "No AI summary available yet."}
          </p>
        )}
      </div>

      <div className="content-grid">
        {/* Extracted profile */}
        <div className="panel green">
          <h2>🐶 Extracted Profile</h2>
          {status === "processing" ? (
            <p style={{ marginTop: 8, color: "#3f5f2f" }}>The Intelligence Worker is extracting skills, experience and embeddings.</p>
          ) : (
            <div style={{ marginTop: 4, display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
                <div>
                  <div style={{ fontWeight: 800, color: "#3f5f2f", fontSize: 11, textTransform: "uppercase" }}>Education</div>
                  <div style={{ fontSize: 15, fontWeight: 700, textTransform: "capitalize" }}>{p.education_level || "—"}</div>
                </div>
                <div>
                  <div style={{ fontWeight: 800, color: "#3f5f2f", fontSize: 11, textTransform: "uppercase" }}>Trajectory</div>
                  <div style={{ fontSize: 15, fontWeight: 700, textTransform: "capitalize" }}>{(p.career_trajectory || "—").toString().replace("_", " ")}</div>
                </div>
              </div>
              <div>
                <div style={{ fontWeight: 800, color: "#3f5f2f", fontSize: 11, textTransform: "uppercase", marginBottom: 8 }}>Skills & Domains</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                  {skillTags.map((skill: string, i: number) => (
                    <span key={i} className="tag" style={{ background: "rgba(255,255,255,0.7)" }}>{skill}</span>
                  ))}
                  {skillTags.length === 0 && <span style={{ color: "#3f5f2f" }}>No skills extracted.</span>}
                </div>
              </div>
              {p.raw_text && (
                <div>
                  <div style={{ fontWeight: 800, color: "#3f5f2f", fontSize: 11, textTransform: "uppercase", marginBottom: 8 }}>Resume Excerpt</div>
                  <pre style={{ background: "rgba(255,255,255,0.55)", padding: 12, borderRadius: 12, whiteSpace: "pre-wrap", fontSize: 12, maxHeight: 150, overflowY: "auto", margin: 0, fontFamily: "inherit" }}>
                    {p.raw_text}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Score breakdown with donut */}
        {candidate.scores && (
          <div className="panel light-orange">
            <h2>📊 AI Match Score</h2>
            <div style={{ display: "flex", alignItems: "center", gap: 24, marginTop: 4 }}>
              {/* Donut */}
              <div style={{ position: "relative", width: 160, height: 160, flexShrink: 0 }}>
                <svg width="160" height="160" viewBox="0 0 160 160">
                  <circle cx="80" cy="80" r={R} fill="none" stroke="rgba(56,18,11,0.10)" strokeWidth="16" />
                  <circle cx="80" cy="80" r={R} fill="none" stroke="#ff7d29" strokeWidth="16" strokeLinecap="round"
                    strokeDasharray={C} strokeDashoffset={C * (1 - overall / 100)} transform="rotate(-90 80 80)"
                    style={{ transition: "stroke-dashoffset 0.6s ease" }} />
                </svg>
                <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                  <div style={{ fontSize: 34, fontWeight: 900, color: "var(--text-main)", lineHeight: 1 }}>{overall}%</div>
                  <div style={{ fontSize: 11, fontWeight: 800, color: "var(--text-muted)", textTransform: "uppercase" }}>Overall</div>
                </div>
              </div>
              {/* Bars */}
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 14 }}>
                {[
                  { label: "Hard Skills", value: hard, color: "#7209b7" },
                  { label: "Soft Skills", value: soft, color: "#ff7d29" },
                  { label: "Experience", value: exp, color: "#f72585" },
                  { label: "Domain", value: domain, color: "#2d6a4f" },
                ].map((bar, idx) => (
                  <div key={idx}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, fontWeight: 800, marginBottom: 5 }}>
                      <span>{bar.label}</span><span style={{ color: bar.color }}>{bar.value}%</span>
                    </div>
                    <div style={{ height: 10, background: "rgba(56,18,11,0.08)", borderRadius: 999, overflow: "hidden" }}>
                      <div style={{ width: `${bar.value}%`, height: "100%", background: bar.color, borderRadius: 999, transition: "width 0.5s ease" }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Interview outcome */}
      <div className="panel green" style={{ marginTop: 24 }}>
        <h2>📅 Interview Outcome</h2>

        {/* Decision / stage banner */}
        {(() => {
          const O: Record<string, { bg: string; color: string; icon: string; title: string; msg: string }> = {
            selected: { bg: "#d8f3dc", color: "#1b4332", icon: "✅", title: "Candidate Selected", msg: "This candidate cleared the interview process and has been selected." },
            rejected: { bg: "#fde2e4", color: "#721c24", icon: "❌", title: "Candidate Rejected", msg: "This candidate was reviewed and did not move forward." },
            interview: { bg: "#e7d3ff", color: "#5a189a", icon: "🎙️", title: "In Interview Process", msg: "Moved to the interview round. Use the Interview Hub to start the interview, then select or reject." },
            interviewing: { bg: "#e7d3ff", color: "#5a189a", icon: "🎙️", title: "In Interview Process", msg: "Moved to the interview round. Use the Interview Hub to start the interview, then select or reject." },
          };
          const o = O[status] || { bg: "rgba(255,255,255,0.6)", color: "#3f5f2f", icon: "⏳", title: "Not in interview yet", msg: "Move this candidate to the Interview Hub to begin the interview process." };
          return (
            <div style={{ background: o.bg, borderLeft: `6px solid ${o.color}`, borderRadius: 14, padding: "16px 18px", margin: "4px 0 20px", display: "flex", alignItems: "center", gap: 14 }}>
              <span style={{ fontSize: 26 }}>{o.icon}</span>
              <div>
                <div style={{ fontWeight: 900, fontSize: 16, color: o.color }}>{o.title}</div>
                <div style={{ fontSize: 13, color: "#3a3a3a", marginTop: 2 }}>{o.msg}</div>
              </div>
            </div>
          );
        })()}
      </div>
    </>
  );
}
