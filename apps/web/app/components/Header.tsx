"use client";

import { useSession } from "next-auth/react";

export default function Header() {
  const { data: session } = useSession();

  return (
    <header className="header-row">
      <input type="text" className="search-bar" placeholder="Search..." />
      {session && (
        <div className="user-profile">
          <img 
            src={session.user?.image || ""} 
            alt="User avatar" 
            className="user-avatar" 
            style={{ objectFit: 'cover' }}
          />
          Welcome back, {session.user?.name?.split(' ')[0]?.toUpperCase() || "USER"}
        </div>
      )}
    </header>
  );
}
