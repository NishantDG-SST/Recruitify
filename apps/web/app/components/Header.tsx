"use client";

export default function Header() {
  return (
    <header className="header-row">
      <input type="text" className="search-bar" placeholder="Search..." />
      <div className="user-profile">
        <div 
          className="user-avatar" 
          style={{ 
            width: '32px', 
            height: '32px', 
            borderRadius: '50%', 
            background: 'var(--accent)', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center', 
            fontWeight: 'bold', 
            color: '#fff', 
            fontSize: '12px' 
          }}
        >
          DU
        </div>
        Welcome back, DEMO USER
      </div>
    </header>
  );
}
