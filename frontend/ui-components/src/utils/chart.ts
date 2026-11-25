import type { TrendSeries } from '../types';
import { isIsoDate } from './format';

/**
 * Union of every x value across all series. ISO dates are sorted chronologically;
 * categorical labels keep their first-seen order.
 */
export function collectXValues(series: TrendSeries[]): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];
  for (const s of series) {
    for (const p of s.points ?? []) {
      if (p && typeof p.x === 'string' && !seen.has(p.x)) {
        seen.add(p.x);
        ordered.push(p.x);
      }
    }
  }
  if (ordered.length > 0 && ordered.every(isIsoDate)) ordered.sort();
  return ordered;
}

/** Aligns a series to the shared x domain; missing x values become `null` (gaps). */
export function alignSeries(series: TrendSeries, xs: string[]): (number | null)[] {
  const map = new Map<string, number | null>();
  for (const p of series.points ?? []) {
    if (!p) continue;
    const y = typeof p.y === 'number' && Number.isFinite(p.y) ? p.y : null;
    map.set(p.x, y);
  }
  return xs.map((x) => (map.has(x) ? (map.get(x) as number | null) : null));
}

/** Largest finite y across all aligned series (0 when empty). */
export function maxValue(aligned: (number | null)[][]): number {
  let max = 0;
  for (const values of aligned) for (const v of values) if (v !== null && v > max) max = v;
  return max;
}

/** Rounds `value` up to a "nice" axis maximum (1, 2, 2.5, 5 × 10ⁿ). Never returns less than 1. */
export function niceMax(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 1;
  const exponent = Math.floor(Math.log10(value));
  const base = Math.pow(10, exponent);
  const fraction = value / base;
  const niceFraction = fraction <= 1 ? 1 : fraction <= 2 ? 2 : fraction <= 2.5 ? 2.5 : fraction <= 5 ? 5 : 10;
  const nice = niceFraction * base;
  return nice < 1 ? 1 : nice;
}

/** Evenly spaced tick values from 0 to `max` inclusive. */
export function yTicks(max: number, count = 4): number[] {
  const step = max / count;
  const ticks: number[] = [];
  for (let i = 0; i <= count; i++) ticks.push(Number((step * i).toFixed(4)));
  return ticks;
}

/**
 * Y-axis scale with readable tick steps (1, 2, 5 × 10ⁿ). When every value is an integer (counts)
 * the step is never fractional, so axes read 0, 2, 4, 6 rather than 0, 1.25, 2.5…
 */
export function niceScale(rawMax: number, options: { targetTicks?: number; integer?: boolean } = {}): { max: number; step: number; ticks: number[] } {
  const targetTicks = options.targetTicks ?? 4;
  const integer = options.integer ?? true;
  if (!Number.isFinite(rawMax) || rawMax <= 0) {
    const step = integer ? 1 : 0.25;
    return { max: step * targetTicks, step, ticks: Array.from({ length: targetTicks + 1 }, (_, i) => round(i * step)) };
  }
  const rawStep = rawMax / targetTicks;
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const residual = rawStep / magnitude;
  let step = (residual <= 1 ? 1 : residual <= 2 ? 2 : residual <= 5 ? 5 : 10) * magnitude;
  if (integer) step = Math.max(1, Math.round(step));
  const max = step * Math.max(1, Math.ceil(rawMax / step - 1e-9));
  const ticks: number[] = [];
  for (let v = 0; v <= max + step / 2; v += step) ticks.push(Number(v.toFixed(6)));
  return { max, step, ticks };
}

/** True when every non-null value is an integer. */
export function allIntegers(aligned: (number | null)[][]): boolean {
  return aligned.every((values) => values.every((v) => v === null || Number.isInteger(v)));
}

/**
 * Builds SVG path strings for a line series. A `null` value breaks the line, so each
 * contiguous run of values becomes its own `M…L…` segment. Runs of a single point are
 * returned as segments with one coordinate pair (rendered as dots by the caller).
 */
export function lineSegments(
  values: (number | null)[],
  xAt: (index: number) => number,
  yAt: (value: number) => number,
): { d: string; points: number }[] {
  const segments: { d: string; points: number }[] = [];
  let current: string[] = [];
  const flush = () => {
    if (current.length) segments.push({ d: current.join(' '), points: current.length });
    current = [];
  };
  values.forEach((v, i) => {
    if (v === null) {
      flush();
      return;
    }
    const cmd = current.length === 0 ? 'M' : 'L';
    current.push(`${cmd}${round(xAt(i))},${round(yAt(v))}`);
  });
  flush();
  return segments;
}

/** Shows at most `maxLabels` x labels by returning the stride between labelled indices. */
export function labelStride(count: number, maxLabels: number): number {
  if (count <= 0 || maxLabels <= 0) return 1;
  return Math.max(1, Math.ceil(count / maxLabels));
}

/** Default series colour from the token palette. */
export function paletteColor(index: number): string {
  return `var(--tp-chart-${(index % 6) + 1})`;
}

export function round(n: number): number {
  return Math.round(n * 100) / 100;
}
