import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  compilerOptions: {
    // Svelte 5 runes everywhere (no legacy `export let`, `$:` or stores).
    runes: true,
  },
  kit: {
    // Static SPA for S3 + CloudFront: every unknown path is served index.html and routed client-side.
    adapter: adapter({
      pages: 'build',
      assets: 'build',
      fallback: 'index.html',
      precompress: false,
      strict: true,
    }),
    alias: {
      $components: 'src/lib/components',
    },
  },
};

export default config;
