/**
 * Registers the @teampulse/ui-components custom elements exactly once, in the browser only.
 *
 * Called from the root `+layout.ts` load function, i.e. before any page renders. Because the
 * elements are defined up-front, Svelte 5 detects their property setters and assigns complex
 * values (arrays, objects) as DOM properties instead of stringified attributes.
 *
 * The tree-shakable `dist-custom-elements` build (`@teampulse/ui-components/components`) is used
 * rather than the lazy loader because it bundles cleanly with Vite.
 */
let registration: Promise<void> | null = null;

export function registerUiComponents(): Promise<void> {
  if (typeof window === 'undefined' || typeof customElements === 'undefined') return Promise.resolve();
  registration ??= import('@teampulse/ui-components/components').then(({ defineCustomElements }) => {
    defineCustomElements();
  });
  return registration;
}

/** Tag names shipped by the library (used by tests and docs). */
export const UI_TAGS = [
  'tp-leaderboard-table',
  'tp-progress-ring',
  'tp-progress-card',
  'tp-trend-chart',
  'tp-badge',
  'tp-stat-tile',
] as const;
