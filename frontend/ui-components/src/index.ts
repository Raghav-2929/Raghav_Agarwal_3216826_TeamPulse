/**
 * @teampulse/ui-components — package entry.
 *
 * Register the elements with either:
 *   import { defineCustomElements } from '@teampulse/ui-components/components'; // bundlers (tree-shakable)
 *   import { defineCustomElements } from '@teampulse/ui-components/loader';     // lazy loader
 *
 * Load the design tokens once:
 *   import '@teampulse/ui-components/tokens.css';
 */
export type {
  Category,
  Tone,
  LeaderboardEntry,
  TeamLeaderboardEntry,
  LeaderboardMode,
  LeaderboardRowSelectDetail,
  TrendPoint,
  TrendSeries,
  TrendChartType,
  TrendPointSelectDetail,
  ProgressCardActionDetail,
} from './types';
export type * from './components.d.ts';

export { parseArrayProp, percentOf, clamp } from './utils/parse';
export { formatShortDate, formatLongDate, formatNumber, categoryIcon, categoryLabel } from './utils/format';

/** Names of the custom events emitted by the components (use these with addEventListener / Svelte `on…` attributes). */
export const TP_EVENTS = {
  rowSelect: 'tp-row-select',
  pointSelect: 'tp-point-select',
  action: 'tp-action',
} as const;
