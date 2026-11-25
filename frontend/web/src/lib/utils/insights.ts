import type { TrendSeries } from '@teampulse/ui-components';
import type { CategoryCount, PersonalInsights, TeamInsights, TeamInsightsDay } from '$lib/api/types';
import { enumerateDays, isValidISODate } from './dates';

/** Label used wherever a k-anonymity–suppressed day is shown. */
export function suppressedLabel(minCohortSize: number): string {
  return `Suppressed (fewer than ${minCohortSize} members)`;
}

/** Personal completions per day over the whole range (days without activity count as 0). */
export function personalDailySeries(insights: Pick<PersonalInsights, 'from' | 'to' | 'daily'>, label = 'Completions'): TrendSeries[] {
  const byDate = new Map(insights.daily.map((d) => [d.date, d.completions]));
  const days = isValidISODate(insights.from) && isValidISODate(insights.to) ? enumerateDays(insights.from, insights.to) : [...byDate.keys()].sort();
  return [{ label, color: 'var(--tp-chart-1)', points: days.map((date) => ({ x: date, y: byDate.get(date) ?? 0 })) }];
}

/**
 * Team trend series. Suppressed days — and, defensively, any day missing from the response —
 * become `null`, which the chart renders as a gap. Values are aggregates only; no member names.
 */
export function teamDailySeries(insights: Pick<TeamInsights, 'from' | 'to' | 'daily'>): TrendSeries[] {
  const byDate = new Map<string, TeamInsightsDay>(insights.daily.map((d) => [d.date, d]));
  const days = isValidISODate(insights.from) && isValidISODate(insights.to) ? enumerateDays(insights.from, insights.to) : [...byDate.keys()].sort();
  const valueOf = (date: string, key: 'completions' | 'active_members') => {
    const day = byDate.get(date);
    if (!day || day.suppressed) return null;
    const v = day[key];
    return typeof v === 'number' ? v : null;
  };
  return [
    { label: 'Completions', color: 'var(--tp-chart-1)', points: days.map((x) => ({ x, y: valueOf(x, 'completions') })) },
    { label: 'Active members', color: 'var(--tp-chart-2)', points: days.map((x) => ({ x, y: valueOf(x, 'active_members') })) },
  ];
}

/** Dates of suppressed days (explicit flag or missing from the response). */
export function suppressedDays(insights: Pick<TeamInsights, 'from' | 'to' | 'daily'>): string[] {
  const byDate = new Map(insights.daily.map((d) => [d.date, d]));
  const days = isValidISODate(insights.from) && isValidISODate(insights.to) ? enumerateDays(insights.from, insights.to) : [...byDate.keys()].sort();
  return days.filter((date) => {
    const day = byDate.get(date);
    return !day || day.suppressed;
  });
}

export interface CategoryShare extends CategoryCount {
  share: number;
}

/** Category counts sorted descending with their share of the total (0–1). */
export function categoryShares(byCategory: CategoryCount[]): CategoryShare[] {
  const total = byCategory.reduce((sum, c) => sum + (c.completions || 0), 0);
  return [...byCategory]
    .filter((c) => c.completions > 0)
    .sort((a, b) => b.completions - a.completions)
    .map((c) => ({ ...c, share: total > 0 ? c.completions / total : 0 }));
}

export function percent(value: number, digits = 0): string {
  if (!Number.isFinite(value)) return '–';
  return `${(value * 100).toFixed(digits)}%`;
}
