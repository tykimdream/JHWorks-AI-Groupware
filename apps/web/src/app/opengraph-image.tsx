import { ImageResponse } from 'next/og';
import { BrandWordmark } from '@/components/brand-mark';

export const alt = 'JHWorks — AI workspace. From request to approval.';
export const size = { width: 1200, height: 630 };
export const contentType = 'image/png';

// Fixed brand artwork only: no employee data, cookies, model calls or remote fonts.
export default function OpenGraphImage() {
  return new ImageResponse(
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', padding: '64px 76px', background: '#f7f8fc', color: '#202735', fontFamily: 'sans-serif' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <BrandWordmark height={44} color="#6554cf" />
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
