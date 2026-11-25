/**
 * Public data shapes accepted by the TeamPulse components.
 * They mirror the TeamPulse REST contract (snake_case) so API payloads can be passed through untouched.
 */

/** Activity type / habit category. */
export type Category = 'fitness' | 'mindfulness' | 'nutrition' | 'sleep' | 'hydration' | 'learning';

/** Colour tone for progress indicators. Categories map to their category colour token. */
export type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'neutral' | Category;

/** A row of an individual challenge leaderboard (`LeaderboardOut.individuals[]`). */
export interface LeaderboardEntry {
  rank: number;
  display_name: string;
  team_name?: string | null;
  score: number;
  goal_reached?: boolean;
  is_me?: boolean;
}

/** A row of a team challenge leaderboard (`LeaderboardOut.teams[]`). */
export interface TeamLeaderboardEntry {
  rank: number;
  team_id?: string;
  team_name: string;
  participants: number;
  total_score: number;
  average_score: number;
}

export type LeaderboardMode = 'individual' | 'team';

/** `detail` of the `tp-row-select` event. */
export interface LeaderboardRowSelectDetail {
  index: number;
  mode: LeaderboardMode;
  entry: LeaderboardEntry | TeamLeaderboardEntry;
}

/** A single point. `y: null` is rendered as a gap (e.g. a k-anonymity–suppressed day). */
export interface TrendPoint {
  /** ISO date (`YYYY-MM-DD`) or any categorical label. */
  x: string;
  y: number | null;
}

export interface TrendSeries {
  label: string;
  points: TrendPoint[];
  /** Any CSS colour, including `var(--tp-…)`. Defaults to the `--tp-chart-N` palette. */
  color?: string;
}

export type TrendChartType = 'line' | 'bar';

/** `detail` of the `tp-point-select` event. */
export interface TrendPointSelectDetail {
  index: number;
  x: string;
  values: { label: string; y: number | null }[];
}

/** `detail` of the `tp-action` event emitted by `tp-progress-card`. */
export interface ProgressCardActionDetail {
  action: string;
}
