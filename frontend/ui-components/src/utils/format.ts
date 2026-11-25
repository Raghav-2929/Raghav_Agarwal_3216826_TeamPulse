import type { Tone } from '../types';

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function isIsoDate(value: string): boolean {
  return ISO_DATE.test(value);
}

/**
 * Formats `YYYY-MM-DD` as `Nov 8` without going through `Date` (no timezone drift).
 * Non-date labels are returned unchanged so the chart can also plot categorical x values.
 */
export function formatShortDate(value: string): string {
  const m = ISO_DATE.exec(value);
  if (!m) return value;
  const month = MONTHS[Number(m[2]) - 1];
  return month ? `${month} ${Number(m[3])}` : value;
}

/** Formats `YYYY-MM-DD` as `Nov 8, 2026`; ISO datetimes are converted to the local calendar date first. */
export function formatLongDate(value: string | null | undefined): string {
  if (!value) return '';
  let iso = value;
  if (value.length > 10 && value.includes('T')) {
    const d = new Date(value);
    if (!Number.isNaN(d.getTime())) iso = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
  }
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return value;
  const month = MONTHS[Number(m[2]) - 1];
  return month ? `${month} ${Number(m[3])}, ${m[1]}` : value;
}

/** Compact number formatting: integers stay integers, others get at most 2 decimals. */
export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '–';
  if (Number.isInteger(value)) return value.toLocaleString('en-US');
  return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
}

const CATEGORY_TONES = ['fitness', 'mindfulness', 'nutrition', 'sleep', 'hydration', 'learning'];

/** Maps a tone to the token that colours it. */
export function toneColor(tone: Tone | string | undefined): string {
  if (tone && CATEGORY_TONES.includes(tone)) return `var(--tp-color-category-${tone})`;
  switch (tone) {
    case 'success':
      return 'var(--tp-color-success)';
    case 'warning':
      return 'var(--tp-color-warning)';
    case 'danger':
      return 'var(--tp-color-danger)';
    case 'neutral':
      return 'var(--tp-color-text-subtle)';
    default:
      return 'var(--tp-color-primary)';
  }
}

export function isCategory(value: string | undefined | null): boolean {
  return !!value && CATEGORY_TONES.includes(value);
}

const CATEGORY_ICONS: Record<string, string> = {
  fitness: '🏃',
  mindfulness: '🧘',
  nutrition: '🥗',
  sleep: '😴',
  hydration: '💧',
  learning: '📚',
};

/** Default emoji for an activity type (used when no `icon` slot is provided). */
export function categoryIcon(category: string | undefined | null): string {
  return (category && CATEGORY_ICONS[category]) || '⭐';
}

/** Human label for a category value (`fitness` → `Fitness`). */
export function categoryLabel(category: string | undefined | null): string {
  if (!category) return '';
  return category.charAt(0).toUpperCase() + category.slice(1);
}

export type DeltaTrend = 'up' | 'down' | 'flat';

/** Direction of a delta given as a number (`-3`) or a display string (`"+12%"`, `"−4"`). */
export function deltaTrend(delta: number | string | null | undefined): DeltaTrend | null {
  if (delta === null || delta === undefined || delta === '') return null;
  if (typeof delta === 'number') {
    if (!Number.isFinite(delta)) return null;
    return delta > 0 ? 'up' : delta < 0 ? 'down' : 'flat';
  }
  const text = String(delta).trim();
  if (/^[-−]/.test(text)) return 'down';
  const numeric = parseFloat(text.replace(/[^0-9.+-]/g, ''));
  if (text.startsWith('+')) return numeric === 0 ? 'flat' : 'up';
  if (Number.isFinite(numeric)) return numeric > 0 ? 'up' : numeric < 0 ? 'down' : 'flat';
  return 'flat';
}

/** Display text for a delta: numbers and plain-number strings get an explicit sign (`+3`); other strings are shown as-is. */
export function formatDelta(delta: number | string | null | undefined): string {
  if (delta === null || delta === undefined || delta === '') return '';
  if (typeof delta === 'number') return delta > 0 ? `+${formatNumber(delta)}` : formatNumber(delta);
  // An HTML attribute always arrives as text: a plain number such as "12" gets the same sign as 12.
  const text = String(delta).trim();
  if (/^-?\d+(\.\d+)?$/.test(text)) return formatDelta(Number(text));
  return String(delta);
}
