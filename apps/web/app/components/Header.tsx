"use client";

import { useSession } from "next-auth/react";

export default function Header() {
  const { data: session } = useSession();

  const name = session?.user?.name || "Recruiter";
  const initials = name
    .split(" ")
    .map((n: string) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <header className="header-row">
      <input type="text" className="search-bar" placeholder="Search..." />
      <div className="user-profile">
        <div
          className="user-avatar"
          style={{
            width: "32px",
            height: "32px",
            borderRadius: "50%",
            background: "var(--accent)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontWeight: "bold",
            color: "#fff",
            fontSize: "12px",
          }}
        >
          {initials}
        </div>
        Welcome back, {name}
      </div>
    </header>
  );
}
