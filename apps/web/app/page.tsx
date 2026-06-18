"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { fetchJobs, fetchCandidates } from "./lib/api";

type JobStat = { job: any; count: number; statuses: string[] };

const STATUS_GROUPS = [
  { key: "extracted", label: "Extracted", color: "#ff9b44", match: (s: string) => s === "extracted" || s === "active" },
  { key: "interview", label: "In Interview", color: "#7209b7", match: (s: string) => s === "interview" || s === "interviewing" },
  { key: "selected", label: "Selected", color: "#2d6a4f", match: (s: string) => s === "selected" },
  { key: "rejected", label: "Rejected", color: "#d90429", match: (s: string) => s === "rejected" },
  { key: "processing", label: "Processing", color: "#f8c067", match: (s: string) => s === "processing" },
];

const SLOTS = 3;
const ROW_COLORS = ["#ffe1c4", "#e7d3ff", "#d3f0c2"]; // peach, lavender, green
const ROW_STYLE: React.CSSProperties = { textDecoration: "none", color: "inherit", height: 60, gap: 0 };
const ELLIPSIS: React.CSSProperties = { overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" };
const CHEVRON: React.CSSProperties = { marginLeft: 12, fontSize: 22, fontWeight: 800, color: "rgba(56,18,11,0.35)", flexShrink: 0 };

function PlaceholderRow() {
  return (
    <div className="ranking-item" style={{ height: 60, opacity: 0.5, background: "rgba(255,255,255,0.35)", border: "1px dashed rgba(56,18,11,0.12)", boxShadow: "none", cursor: "default" }}>
      <div className="ranking-avatar" style={{ background: "rgba(56,18,11,0.07)", flexShrink: 0 }} />
      <div className="ranking-info"><div className="ranking-desc">—</div></div>
    </div>
  );
}

export default function Home() {
  const [jobs, setJobs] = useState<any[]>([]);
  const [candidates, setCandidates] = useState<any[]>([]);
  const [jobStats, setJobStats] = useState<JobStat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const j = (await fetchJobs()).jobs || [];
        setJobs(j);
        const all = (await fetchCandidates("all")).candidates || [];
        setCandidates(all);
        const perJob = await Promise.all(
          j.map(async (job: any) => {
            const cs = (await fetchCandidates(job.id)).candidates || [];
            return { job, count: cs.length, statuses: cs.map((c: any) => c.status) } as JobStat;
          })
        );
        setJobStats(perJob);
      } catch (e) {
        console.error(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  // Aggregates
  const allStatuses = jobStats.flatMap((s) => s.statuses);
  const totalCandidates = allStatuses.length || candidates.length;
  const statusCounts = STATUS_GROUPS.map((g) => ({ ...g, value: allStatuses.filter((s) => g.match(s)).length }));
  const inInterview = statusCounts.find((s) => s.key === "interview")?.value || 0;
  const selected = statusCounts.find((s) => s.key === "selected")?.value || 0;

  // Donut geometry
  const R = 70, C = 2 * Math.PI * R;
  const donutTotal = statusCounts.reduce((a, b) => a + b.value, 0) || 1;
  let acc = 0;
  const donutSegments = statusCounts.filter((s) => s.value > 0).map((s) => {
    const dash = (s.value / donutTotal) * C;
    const seg = { ...s, dash, offset: acc };
    acc += dash;
    return seg;
  });

  // Bar chart
  const maxCount = Math.max(1, ...jobStats.map((s) => s.count));
  const niceMax = Math.max(5, Math.ceil(maxCount / 5) * 5);
  const ticks = [1, 0.75, 0.5, 0.25, 0].map((f) => Math.round(niceMax * f)); // top→bottom
  const BAR_PALETTE = ["#7209b7", "#ff7d29", "#2d6a4f", "#4361ee", "#f72585", "#f8c067"];

  const IconBadge = ({ children, bg = "rgba(56,18,11,0.85)" }: { children: any; bg?: string }) => (
    <span style={{ width: 38, height: 38, borderRadius: "50%", background: bg, color: "#fff", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>{children}</span>
  );

  return (
    <>
      <h1 className="page-title">Good Morning</h1>
      <p className="page-subtitle">Here's today's overview of your hiring pipeline.</p>

      {/* Stat cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 20 }}>
        {[
          { label: "Active Jobs", value: jobs.length, icon: "📋", bg: "linear-gradient(135deg, #b388ff, #d3b4f6)", color: "#2a1a4a", trend: "Live requisitions" },
          { label: "Total Candidates", value: totalCandidates, icon: "👥", bg: "linear-gradient(135deg, #ff9b44, #ffb87a)", color: "#5a2c00", trend: "Across all jobs" },
          { label: "In Interview", value: inInterview, icon: "🎙️", bg: "linear-gradient(135deg, #4c7cff, #8fb2ff)", color: "#0a2a66", trend: `${selected} selected` },
          { label: "Selected", value: selected, icon: "✅", bg: "linear-gradient(135deg, #38b06f, #8fe3ad)", color: "#0d3d24", trend: "Offers extended" },
        ].map((card) => (
          <div key={card.label} className="stat-card" style={{ background: card.bg, color: card.color, minHeight: 168, display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
            <div className="stat-title" style={{ color: card.color }}><IconBadge bg="rgba(255,255,255,0.3)">{card.icon}</IconBadge> {card.label}</div>
            <div className="stat-value" style={{ margin: "12px 0 6px" }}>{card.value}</div>
            <div className="stat-trend" style={{ background: "rgba(255,255,255,0.45)", color: card.color }}>{card.trend}</div>
          </div>
        ))}
      </div>

      {/* Charts row */}
      <div className="content-grid" style={{ marginTop: 24 }}>
        {/* Candidates per job — bar chart */}
        <div className="panel light-orange">
          <h2>📊 Candidates per Job</h2>
          {loading ? (
            <p style={{ color: "#6b5a52" }}>Loading…</p>
          ) : jobStats.length === 0 ? (
            <p style={{ color: "#6b5a52" }}>No jobs yet.</p>
          ) : (
            <div style={{ display: "flex", gap: 14, marginTop: 18 }}>
              {/* Y axis */}
              <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", height: 150, fontSize: 11, fontWeight: 800, color: "var(--text-muted)" }}>
                {ticks.map((t, i) => <span key={i} style={{ lineHeight: 1 }}>{t}</span>)}
              </div>
              {/* Plot */}
              <div style={{ flex: 1, position: "relative", height: 180 }}>
                {/* gridlines */}
                {ticks.map((_, i) => (
                  <div key={i} style={{ position: "absolute", left: 0, right: 0, top: `${(i / (ticks.length - 1)) * 150}px`, borderTop: "1px dashed rgba(56,18,11,0.12)" }} />
                ))}
                {/* bars */}
                <div style={{ position: "absolute", left: 0, right: 0, top: 0, bottom: 30, display: "flex", alignItems: "flex-end", gap: 28, overflowX: "auto" }}>
                  {jobStats.map((s, i) => {
                    const h = Math.round((s.count / niceMax) * 150);
                    const color = BAR_PALETTE[i % BAR_PALETTE.length];
                    return (
                      <div key={i} style={{ flex: 1, minWidth: 48, height: "100%", display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "flex-end" }}>
                        <div style={{ fontWeight: 900, fontSize: 14, color, marginBottom: 4 }}>{s.count}</div>
                        <div title={s.job.title} style={{ width: "100%", maxWidth: 58, height: Math.max(h, 4), borderRadius: "10px 10px 4px 4px", background: `linear-gradient(180deg, ${color}, ${color}bb)`, boxShadow: `0 8px 16px ${color}33`, transition: "height 0.5s ease" }} />
                      </div>
                    );
                  })}
                </div>
                {/* X axis labels */}
                <div style={{ position: "absolute", left: 0, right: 0, bottom: 0, height: 28, display: "flex", gap: 28, alignItems: "center" }}>
                  {jobStats.map((s, i) => (
                    <div key={i} title={s.job.title} style={{ flex: 1, minWidth: 48, textAlign: "center", fontSize: 11, fontWeight: 800, color: "var(--text-main)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                      {s.job.title}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Pipeline status — donut */}
        <div className="panel green">
          <h2>🩺 Pipeline Status</h2>
          {loading ? (
            <p style={{ color: "#3f5f2f" }}>Loading…</p>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 24, marginTop: 4 }}>
              <div style={{ position: "relative", width: 170, height: 170, flexShrink: 0 }}>
                <svg width="170" height="170" viewBox="0 0 170 170">
                  <circle cx="85" cy="85" r={R} fill="none" stroke="rgba(56,18,11,0.08)" strokeWidth="18" />
                  {donutSegments.map((seg, i) => (
                    <circle key={i} cx="85" cy="85" r={R} fill="none" stroke={seg.color} strokeWidth="18"
                      strokeDasharray={`${seg.dash} ${C - seg.dash}`} strokeDashoffset={-seg.offset}
                      transform="rotate(-90 85 85)" strokeLinecap="butt"
                      style={{ transition: "stroke-dasharray 0.6s ease" }} />
                  ))}
                </svg>
                <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center" }}>
                  <div style={{ fontSize: 30, fontWeight: 900, lineHeight: 1 }}>{totalCandidates}</div>
                  <div style={{ fontSize: 11, fontWeight: 800, color: "#3f5f2f", textTransform: "uppercase" }}>Candidates</div>
                </div>
              </div>
              <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 10 }}>
                {statusCounts.map((s) => (
                  <div key={s.key} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontSize: 13, fontWeight: 700 }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ width: 12, height: 12, borderRadius: 3, background: s.color, display: "inline-block" }} />
                      {s.label}
                    </span>
                    <span style={{ fontWeight: 900 }}>{s.value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Lists row */}
      <div className="content-grid" style={{ marginTop: 24, alignItems: "stretch" }}>
        {/* Recent jobs */}
        <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>💼 Recent Jobs</h2>
            <Link href="/jobs" style={{ fontSize: 12, fontWeight: 800, color: "#7209b7", textDecoration: "none" }}>View all →</Link>
          </div>
          <div className="ranking-list" style={{ marginTop: 16, gap: 10, flex: 1 }}>
            {jobs.length === 0 && <p style={{ color: "#6b5a52" }}>No jobs yet. Create a job to get started.</p>}
            {Array.from({ length: SLOTS }).map((_, idx) => {
              const job = jobs[idx];
              if (!job) return jobs.length > 0 ? <PlaceholderRow key={`p${idx}`} /> : null;
              const stat = jobStats.find((s) => s.job.id === job.id);
              return (
                <Link className="ranking-item" key={job.id} href={`/jobs/${job.id}/rankings`} style={{ ...ROW_STYLE, background: ROW_COLORS[idx % ROW_COLORS.length] }}>
                  <div className="ranking-avatar" style={{ display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18, flexShrink: 0 }}>💼</div>
                  <div className="ranking-info" style={{ minWidth: 0 }}>
                    <div className="ranking-name" style={ELLIPSIS}>{job.title}</div>
                    <div className="ranking-desc">{job.created_at ? new Date(job.created_at).toLocaleDateString() : ""}</div>
                  </div>
                  <span className="tag" style={{ fontWeight: 800, whiteSpace: "nowrap" }}>{stat ? `${stat.count} candidates` : job.status}</span>
                  <span style={CHEVRON}>›</span>
                </Link>
              );
            })}
          </div>
        </div>

        {/* Recent candidates */}
        <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>👤 Recent Candidates</h2>
            <Link href="/candidates" style={{ fontSize: 12, fontWeight: 800, color: "#7209b7", textDecoration: "none" }}>View all →</Link>
          </div>
          <div className="ranking-list" style={{ marginTop: 16, gap: 10, flex: 1 }}>
            {candidates.length === 0 && <p style={{ color: "#6b5a52" }}>No candidates yet.</p>}
            {Array.from({ length: SLOTS }).map((_, idx) => {
              const c = candidates[idx];
              if (!c) return candidates.length > 0 ? <PlaceholderRow key={`p${idx}`} /> : null;
              const sg = STATUS_GROUPS.find((g) => g.match(c.status));
              return (
                <Link className="ranking-item" key={c.id} href={`/candidates/${c.id}`} style={{ ...ROW_STYLE, background: ROW_COLORS[idx % ROW_COLORS.length] }}>
                  <div className="ranking-avatar" style={{ display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 900, color: "#fff", fontSize: 14, flexShrink: 0 }}>
                    {(c.name || "?").split(" ").map((n: string) => n[0]).join("").toUpperCase().slice(0, 2)}
                  </div>
                  <div className="ranking-info" style={{ minWidth: 0 }}>
                    <div className="ranking-name" style={ELLIPSIS}>{c.name}</div>
                    <div className="ranking-desc" style={ELLIPSIS}>{c.role}</div>
                  </div>
                  <span className="tag" style={{ textTransform: "uppercase", fontSize: 10, fontWeight: 800, whiteSpace: "nowrap", background: sg ? `${sg.color}22` : undefined, color: sg?.color }}>
                    {c.status}
                  </span>
                  <span style={CHEVRON}>›</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
