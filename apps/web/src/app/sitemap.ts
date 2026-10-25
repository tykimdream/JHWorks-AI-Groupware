import type { MetadataRoute } from 'next';
import { siteOrigin } from '@/lib/site-metadata';

export default function sitemap(): MetadataRoute.Sitemap {
  return ['/login', '/pattern'].map((path) => ({ url: `${siteOrigin}${path}` }));
}
