import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

const GATEWAY = process.env.TEAMPULSE_GATEWAY_URL ?? 'http://localhost:8000';
const proxy = {
  '/api': { target: GATEWAY, changeOrigin: true },
  '/.well-known': { target: GATEWAY, changeOrigin: true },
};

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    strictPort: true,
    // The UI library is consumed as a package via `file:../ui-components` (a symlink in
    // node_modules); allow Vite to serve its built files from outside this folder.
    fs: { allow: ['../ui-components'] },
    proxy,
  },
  preview: { port: 4173, proxy },
  test: {
    projects: [
      {
        // Pure logic in src/lib (no DOM).
        extends: true,
        test: {
          name: 'unit',
          environment: 'node',
          include: ['src/**/*.test.ts'],
          exclude: ['src/**/*.svelte.test.ts'],
        },
      },
      {
        // Svelte components + the real custom elements in a DOM.
        extends: true,
        resolve: { conditions: ['browser'] },
        test: {
          name: 'dom',
          environment: 'jsdom',
          include: ['src/**/*.svelte.test.ts'],
        },
      },
    ],
  },
});
