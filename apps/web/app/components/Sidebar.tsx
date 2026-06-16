"use client";

import Link from 'next/link';
import { usePathname } from 'next/navigation';

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="sidebar">
      <div className="brand">RECRUIT IQ</div>
      
      <nav style={{ flex: 1 }}>
        <Link href="/" className={`nav-item ${pathname === '/' ? 'active' : ''}`}>Dashboard</Link>
        <Link href="/jobs" className={`nav-item ${pathname.startsWith('/jobs') ? 'active' : ''}`}>Jobs</Link>
        <Link href="/candidates" className={`nav-item ${pathname.startsWith('/candidates') ? 'active' : ''}`}>Candidates</Link>
        <Link href="/interviews" className={`nav-item ${pathname.startsWith('/interviews') ? 'active' : ''}`}>Interviews</Link>
      </nav>

      <div className="sidebar-bottom">
        <Link href="/settings" className={`nav-item ${pathname.startsWith('/settings') ? 'active' : ''}`}>Settings</Link>
        
        <div style={{ marginTop: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <div 
            style={{ 
              width: '40px', 
              height: '40px', 
              borderRadius: '50%', 
              background: '#ffb87a', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              fontWeight: 'bold', 
              color: 'var(--bg-sidebar)' 
            }}
          >
            DU
          </div>
          <div style={{ fontSize: '14px', lineHeight: '1.2' }}>
            <strong>Demo User 1</strong><br/>
            <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.6)' }}>Admin</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
