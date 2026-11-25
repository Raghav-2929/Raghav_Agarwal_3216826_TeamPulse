/**
 * Date helpers working on `YYYY-MM-DD` strings in the user's local calendar
 * (the API's `date` type), avoiding UTC drift from `Date#toISOString()`.
 */

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/;
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAY_MS = 86_400_000;

export function pad2(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

/** Local calendar date of `d` as `YYYY-MM-DD`. */
export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

export function todayISO(now: Date = new Date()): string {
  return toISODate(now);
}

export function isValidISODate(value: unknown): value is string {
  if (typeof value !== 'string') return false;
  const m = ISO_DATE.exec(value);
  if (!m) return false;
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const date = new Date(Date.UTC(y, mo - 1, d));
  return date.getUTCFullYear() === y && date.getUTCMonth() === mo - 1 && date.getUTCDate() === d;
}

/** Days since epoch for a `YYYY-MM-DD` (UTC arithmetic, so DST never shifts results). */
function dayNumber(iso: string): number {
  const m = ISO_DATE.exec(iso);
  if (!m) throw new Error(`Invalid ISO date: ${iso}`);
  return Math.round(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])) / DAY_MS);
}

function fromDayNumber(n: number): string {
  const d = new Date(n * DAY_MS);
  return `${d.getUTCFullYear()}-${pad2(d.getUTCMonth() + 1)}-${pad2(d.getUTCDate())}`;
}

export function addDays(iso: string, days: number): string {
  return fromDayNumber(dayNumber(iso) + days);
}

/** Whole days from `from` to `to` (positive when `to` is later). */
export function diffDays(from: string, to: string): number {
  return dayNumber(to) - dayNumber(from);
}

/** Every date from `from` to `to`, inclusive. */
export function enumerateDays(from: string, to: string): string[] {
  const start = dayNumber(from);
  const end = dayNumber(to);
  const out: string[] = [];
  for (let n = start; n <= end; n++) out.push(fromDayNumber(n));
  return out;
}

// ------------------------------------------------------------------ range presets

export type RangePresetId = '7d' | '14d' | '30d' | '90d' | '180d' | 'custom';

export interface RangePreset {
  id: Exclude<RangePresetId, 'custom'>;
  label: string;
  days: number;
}

export const RANGE_PRESETS: readonly RangePreset[] = [
  { id: '7d', label: 'Last 7 days', days: 7 },
  { id: '14d', label: 'Last 14 days', days: 14 },
  { id: '30d', label: 'Last 30 days', days: 30 },
  { id: '90d', label: 'Last 90 days', days: 90 },
  { id: '180d', label: 'Last 180 days', days: 180 },
] as const;

export const MAX_RANGE_DAYS = 180;

export interface DateRange {
  from: string;
  to: string;
}

/** "Last N days" including today. */
export function presetRange(id: RangePreset['id'], today: string = todayISO()): DateRange {
  const preset = RANGE_PRESETS.find((p) => p.id === id) ?? RANGE_PRESETS[2];
  return { from: addDays(today, -(preset.days - 1)), to: today };
}

/** Which preset (if any) a range corresponds to. */
export function detectPreset(range: Partial<DateRange>, today: string = todayISO()): RangePresetId {
  if (!range.from || !range.to) return 'custom';
  for (const p of RANGE_PRESETS) {
    const r = presetRange(p.id, today);
    if (r.from === range.from && r.to === range.to) return p.id;
  }
  return 'custom';
}

/**
 * Validates a date range; returns a user-facing message or `null`.
 * The insight endpoints accept at most 180 days.
 */
export function validateRange(
  range: Partial<DateRange>,
  options: { maxDays?: number; allowFuture?: boolean; today?: string; required?: boolean } = {},
): string | null {
  const { maxDays = MAX_RANGE_DAYS, allowFuture = false, today = todayISO(), required = true } = options;
  const { from, to } = range;
  if (!from && !to) return required ? 'Choose a start and end date.' : null;
  if (from && !isValidISODate(from)) return 'Start date is not a valid date.';
  if (to && !isValidISODate(to)) return 'End date is not a valid date.';
  if (required && (!from || !to)) return 'Choose both a start and an end date.';
  if (from && to && diffDays(from, to) < 0) return 'The start date must be on or before the end date.';
  if (!allowFuture && to && diffDays(today, to) > 0) return 'The end date cannot be in the future.';
  if (from && to && maxDays > 0 && diffDays(from, to) + 1 > maxDays) return `Choose a range of at most ${maxDays} days.`;
  return null;
}

// ------------------------------------------------------------------ formatting

/**
 * `2026-11-08` → `Nov 8, 2026`. ISO datetimes (UTC timestamps such as `created_at`) are first
 * converted to the user's local calendar date.
 */
export function formatDate(value: string | null | undefined): string {
  if (!value) return '';
  let iso = value;
  if (value.length > 10 && value.includes('T')) {
    const d = new Date(value);
    if (!Number.isNaN(d.getTime())) iso = toISODate(d);
  }
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return value;
  return `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}, ${m[1]}`;
}

/** `2026-11-08` → `Nov 8`. */
export function formatShortDate(value: string | null | undefined): string {
  if (!value) return '';
  const m = ISO_DATE.exec(value);
  if (!m) return value;
  return `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}`;
}

/** Local date + time for an ISO timestamp. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '';
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return value;
  return `${formatDate(toISODate(d))}, ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
}

/** "just now", "5 min ago", "3 h ago", "2 d ago", or a date for older timestamps. */
export function relativeTime(value: string | null | undefined, now: Date = new Date()): string {
  if (!value) return '';
  const t = new Date(value).getTime();
  if (Number.isNaN(t)) return value;
  const seconds = Math.round((now.getTime() - t) / 1000);
  if (seconds < 45) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return formatDate(toISODate(new Date(t)));
}

/** Human description of a range, e.g. `Nov 1 – Nov 8, 2026`. */
export function formatRange(range: Partial<DateRange>): string {
  if (!range.from || !range.to) return '';
  const sameYear = range.from.slice(0, 4) === range.to.slice(0, 4);
  return `${sameYear ? formatShortDate(range.from) : formatDate(range.from)} – ${formatDate(range.to)}`;
}
