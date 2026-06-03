"use client";

export default function SettingsPage() {
  return (
    <>
      <h1 className="page-title">Settings</h1>
      <p className="page-subtitle">Configure models, thresholds, and organizational rules.</p>

      <div className="content-grid">
        <div className="panel light-orange">
          <h2>LLM Configuration</h2>
          
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontWeight: 800, marginBottom: '8px' }}>Active LLM Provider</label>
            <select className="search-bar" style={{ width: '100%', background: 'rgba(255,255,255,0.8)' }}>
              <option>Google Gemini (gemini-1.5-flash)</option>
              <option>OpenAI (gpt-4o)</option>
              <option>Local (llama-3)</option>
            </select>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontWeight: 800, marginBottom: '8px' }}>Embedding Model</label>
            <select className="search-bar" style={{ width: '100%', background: 'rgba(255,255,255,0.8)' }}>
              <option>text-embedding-004 (Gemini)</option>
              <option>text-embedding-3-small (OpenAI)</option>
            </select>
          </div>
          
          <button className="pill-button">Save Configuration</button>
        </div>

        <div className="panel green">
          <h2>Ranking Thresholds</h2>
          
          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontWeight: 800, marginBottom: '8px' }}>Minimum Match Score</label>
            <input type="range" min="0" max="100" defaultValue="65" style={{ width: '100%' }} />
            <div style={{ textAlign: 'right', fontSize: '12px', fontWeight: 700 }}>65%</div>
          </div>

          <div style={{ marginBottom: '20px' }}>
            <label style={{ display: 'block', fontWeight: 800, marginBottom: '8px' }}>Strict Must-Have Enforcement</label>
            <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px' }}>
              <input type="checkbox" defaultChecked />
              Reject candidates instantly if missing must-haves
            </label>
          </div>
        </div>
      </div>
    </>
  );
}
