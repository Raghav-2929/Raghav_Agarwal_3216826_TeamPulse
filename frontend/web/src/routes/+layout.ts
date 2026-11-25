import { browser } from '$app/environment';
import { registerUiComponents } from '$lib/ui/register';
import type { LayoutLoad } from './$types';

// Pure client-side SPA (served from S3/CloudFront with an index.html fallback).
export const ssr = false;
export const prerender = false;
export const trailingSlash = 'never';

export const load: LayoutLoad = async () => {
  // Define the custom elements before the first page renders.
  if (browser) await registerUiComponents();
  return {};
};
