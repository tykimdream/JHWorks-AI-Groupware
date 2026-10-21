import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    // Build-time only: fixed internal upstream, never derived from user input.
    const target = process.env.API_PROXY_TARGET;
    if (!target) return [];
    const url = new URL(target);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
        url.pathname !== '/' || url.search || url.hash) {
      throw new Error('API_PROXY_TARGET must be an HTTP(S) origin without credentials or a path');
    }
    return [{ source: '/api/v1/:path*', destination: `${url.origin}/api/v1/:path*` }];
  },
};

export default nextConfig;

