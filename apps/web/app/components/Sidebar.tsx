"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { signOut, useSession } from 'next-auth/react';

export default function Sidebar() {
  const pathname = usePathname();
  const { data: session } = useSession();

  return (
    <aside className="sidebar">
      <div className="brand">RECRUIT IQ</div>
      
      <nav style={{ flex: 1 }}>
        <Link href="/" className={`nav-item ${pathname === '/' ? 'active' : ''}`}>Dashboard</Link>
        <Link href="/jobs" className={`nav-item ${pathname.startsWith('/jobs') ? 'active' : ''}`}>Jobs</Link>
        <Link href="/candidates" className={`nav-item ${pathname.startsWith('/candidates') ? 'active' : ''}`}>Candidates</Link>
        <Link href="/interviews" className={`nav-item ${pathname.startsWith('/interviews') ? 'active' : ''}`}>Interviews</Link>
      </nav>

      <div className="sidebar-bottom" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
        <Link href="/settings" className={`nav-item ${pathname.startsWith('/settings') ? 'active' : ''}`} style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>
            <circle cx="12" cy="12" r="3"/>
          </svg>
          Settings
        </Link>
        
        <Link href="#" className="nav-item" onClick={(e) => { e.preventDefault(); signOut({ callbackUrl: "/api/auth/signin" }); }} style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
            <polyline points="16 17 21 12 16 7"/>
            <line x1="21" y1="12" x2="9" y2="12"/>
          </svg>
          Logout
        </Link>
        
        <div style={{ marginTop: '16px', display: 'flex', alignItems: 'center', gap: '12px', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '16px' }}>
          <div style={{ width: '40px', height: '40px', borderRadius: '50%', overflow: 'hidden', flexShrink: 0, boxShadow: '0 4px 10px rgba(0,0,0,0.15)' }}>
            <svg width="40" height="40" viewBox="0 0 100 100">
              <circle cx="50" cy="50" r="50" fill="#f4a261" />
              <circle cx="50" cy="45" r="22" fill="#e0a96d" />
              <path d="M30 40c0-10 10-15 20-15s20 5 20 15v10c0 10-5 18-20 18s-20-8-20-18V40z" fill="#2b110c" />
              <circle cx="50" cy="43" r="20" fill="#e0a96d" />
              <rect x="34" y="38" width="12" height="8" rx="2" fill="none" stroke="#2b110c" strokeWidth="3" />
              <rect x="54" y="38" width="12" height="8" rx="2" fill="none" stroke="#2b110c" strokeWidth="3" />
              <line x1="46" y1="42" x2="54" y2="42" stroke="#2b110c" strokeWidth="3" />
              <circle cx="40" cy="42" r="2" fill="#2b110c" />
              <circle cx="60" cy="42" r="2" fill="#2b110c" />
              <path d="M50 42v5" stroke="#2b110c" strokeWidth="2" strokeLinecap="round" />
              <path d="M46 51q4 3 8 0" stroke="#2b110c" strokeWidth="2" strokeLinecap="round" fill="none" />
              <path d="M25 80c0-15 15-20 25-20s25 5 25 20v10H25V80z" fill="#38120b" />
              <path d="M43 60l7 10 7-10" fill="#e0a96d" />
            </svg>
          </div>
          <div style={{ fontSize: '13px', lineHeight: '1.3' }}>
            <strong style={{ color: '#ffffff' }}>{session?.user?.name || 'Recruiter'}</strong><br/>
            <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)' }}>{session?.user?.email || 'Not signed in'}</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
