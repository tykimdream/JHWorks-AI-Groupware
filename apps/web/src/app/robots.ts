import type { MetadataRoute } from 'next';
import { siteOrigin } from '@/lib/site-metadata';

export default function robots(): MetadataRoute.Robots {
  // Allow HTML crawling so noindex can be read. API authorization remains server-side.
  return { rules: { userAgent: '*', allow: '/', disallow: '/api/' }, sitemap: `${siteOrigin}/sitemap.xml` };
}
