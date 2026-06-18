"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { signIn } from "next-auth/react";

export default function SignupPage() {
  const router = useRouter();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await fetch("/api/users/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, full_name: fullName }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setError(data.detail || "Could not create account.");
        setLoading(false);
        return;
      }
      // Auto sign-in after successful registration.
      const login = await signIn("credentials", { email, password, redirect: false });
      setLoading(false);
      if (login?.ok) {
        router.push("/");
        router.refresh();
      } else {
        router.push("/login");
      }
    } catch {
      setError("Could not create account. Please try again.");
      setLoading(false);
    }
  };

  return (
    <div style={overlay}>
      <div style={card}>
        <div style={{ fontWeight: 900, fontSize: 26, color: "var(--bg-sidebar-hover)", textTransform: "uppercase", textAlign: "center", marginBottom: 4 }}>Recruit IQ</div>
        <p style={{ textAlign: "center", color: "var(--text-muted)", fontWeight: 700, marginTop: 0, marginBottom: 20 }}>Create your workspace</p>
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <label style={lbl}>Full name
            <input type="text" required value={fullName} onChange={(e) => setFullName(e.target.value)} style={input} placeholder="Jane Doe" />
          </label>
          <label style={lbl}>Email
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} style={input} placeholder="you@example.com" />
          </label>
          <label style={lbl}>Password
            <input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} style={input} placeholder="At least 6 characters" />
          </label>
          {error && <div style={{ color: "#d90429", fontSize: 13, fontWeight: 700 }}>{error}</div>}
          <button type="submit" disabled={loading} className="pill-button" style={{ background: "var(--bg-sidebar-hover)", color: "#fff", padding: "12px", fontSize: 15, marginTop: 4 }}>
            {loading ? "Creating account…" : "Sign Up"}
          </button>
        </form>
        <p style={{ textAlign: "center", fontSize: 13, color: "var(--text-muted)", marginTop: 18 }}>
          Already have an account? <Link href="/login" style={{ color: "var(--bg-sidebar-hover)", fontWeight: 800 }}>Sign in</Link>
        </p>
      </div>
    </div>
  );
}

const overlay: React.CSSProperties = { position: "fixed", inset: 0, zIndex: 1000, background: "var(--bg-page)", display: "flex", alignItems: "center", justifyContent: "center", padding: 20 };
const card: React.CSSProperties = { background: "#fff", borderRadius: 24, padding: "36px 32px", width: "100%", maxWidth: 400, boxShadow: "0 20px 50px rgba(0,0,0,0.15)" };
const lbl: React.CSSProperties = { display: "flex", flexDirection: "column", gap: 6, fontSize: 12, fontWeight: 800, color: "var(--text-main)", textTransform: "uppercase" };
const input: React.CSSProperties = { padding: "12px 14px", borderRadius: 12, border: "1px solid #ddd", fontSize: 15, fontFamily: "inherit", outline: "none" };
