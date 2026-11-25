/**
 * Svelte template typings for the @teampulse/ui-components custom elements.
 *
 * Props are typed from the component library's generated `Components` namespace (camelCase
 * property names — Svelte 5 sets them as DOM *properties* because the elements are registered
 * before the app renders, so arrays/objects are passed without JSON serialisation).
 *
 * Events are dash-cased (`tp-row-select`, …). Svelte 5 event attributes are case-sensitive and
 * take the event name verbatim after `on`, so they are written `ontp-row-select={…}`.
 */
import type {
  Components,
  LeaderboardRowSelectDetail,
  ProgressCardActionDetail,
  TrendPointSelectDetail,
} from '@teampulse/ui-components';
import type { HTMLAttributes } from 'svelte/elements';

type ElementProps<T> = Partial<T> & Omit<HTMLAttributes<HTMLElement>, keyof T>;

declare module 'svelte/elements' {
  export interface SvelteHTMLElements {
    'tp-leaderboard-table': ElementProps<Components.TpLeaderboardTable> & {
      'ontp-row-select'?: (event: CustomEvent<LeaderboardRowSelectDetail>) => void;
    };
    'tp-progress-ring': ElementProps<Components.TpProgressRing>;
    'tp-progress-card': ElementProps<Components.TpProgressCard> & {
      'ontp-action'?: (event: CustomEvent<ProgressCardActionDetail>) => void;
    };
    'tp-trend-chart': ElementProps<Components.TpTrendChart> & {
      'ontp-point-select'?: (event: CustomEvent<TrendPointSelectDetail>) => void;
    };
    'tp-badge': ElementProps<Components.TpBadge>;
    'tp-stat-tile': ElementProps<Components.TpStatTile>;
  }
}

export {};
