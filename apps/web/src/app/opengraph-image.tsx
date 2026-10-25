import { ImageResponse } from 'next/og';

export const alt = 'JHWorks — AI workspace. From request to approval.';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

// Fixed brand artwork only: no employee data, cookies, model calls or remote fonts.
export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', padding: '64px 76px', background: '#f5f7fc', color: '#18243b', fontFamily: 'sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
        <svg viewBox="0 0 40 40" width="64" height="64" fill="none">
          <rect width="40" height="40" rx="12" fill="#6554cf" />
          <path d="M14 12v13a5 5 0 0 1-5 5M22 12v16m0-8a6 6 0 0 1 6-6v14" stroke="white" strokeWidth="3.5" strokeLinecap="round" />
          <circle cx="14" cy="7" r="1.8" fill="white" />
        </svg>
        <span style={{ fontSize: 44, fontWeight: 700, letterSpacing: -2 }}>JHWorks</span>
        <span style={{ marginLeft: 'auto', color: '#52617a', fontSize: 20 }}>AI WORKSPACE</span>
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', marginTop: 66, fontSize: 76, fontWeight: 700, letterSpacing: -4, lineHeight: 1.1 }}>
        <span>From request</span><span style={{ color: '#6554cf' }}>to approval.</span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', marginTop: 'auto', paddingTop: 26, borderTop: '1px solid #dbe1ed', fontSize: 22, color: '#52617a' }}>
        <span>Expenses · Approvals · JHW Pattern</span>
        <span style={{ marginLeft: 'auto' }}>groupware.pikan.dev</span>
      </div>
    </div>, size,
  );
}
