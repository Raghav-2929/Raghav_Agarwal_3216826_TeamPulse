import { describe, expect, it } from 'vitest';
import { categoryShares, percent, personalDailySeries, suppressedDays, suppressedLabel, teamDailySeries } from './insights';

describe('team (k-anonymised) series', () => {
  const insights = {
    from: '2026-11-01',
    to: '2026-11-04',
    daily: [
      { date: '2026-11-01', completions: 9, active_members: 4, suppressed: false },
      { date: '2026-11-02', completions: null, active_members: null, suppressed: true },
      { date: '2026-11-03', completions: 7, active_members: 3, suppressed: false },
      // 2026-11-04 missing from the response → treated as suppressed
    ],
  };

  it('renders suppressed and missing days as null gaps', () => {
    const [completions, members] = teamDailySeries(insights);
    expect(completions.points).toEqual([
      { x: '2026-11-01', y: 9 },
      { x: '2026-11-02', y: null },
      { x: '2026-11-03', y: 7 },
      { x: '2026-11-04', y: null },
    ]);
    expect(members.points.map((p) => p.y)).toEqual([4, null, 3, null]);
  });

  it('contains aggregate series labels only (no person names)', () => {
    expect(teamDailySeries(insights).map((s) => s.label)).toEqual(['Completions', 'Active members']);
  });

  it('lists suppressed days and labels them', () => {
    expect(suppressedDays(insights)).toEqual(['2026-11-02', '2026-11-04']);
    expect(suppressedLabel(3)).toBe('Suppressed (fewer than 3 members)');
  });
});

describe('personal series and categories', () => {
  it('fills days without activity with zero', () => {
    const [series] = personalDailySeries({ from: '2026-11-01', to: '2026-11-03', daily: [{ date: '2026-11-02', completions: 2, value: 2 }] });
    expect(series.points).toEqual([
      { x: '2026-11-01', y: 0 },
      { x: '2026-11-02', y: 2 },
      { x: '2026-11-03', y: 0 },
    ]);
  });

  it('computes category shares sorted by completions', () => {
    const shares = categoryShares([
      { category: 'sleep', completions: 1 },
      { category: 'fitness', completions: 3 },
      { category: 'learning', completions: 0 },
    ]);
    expect(shares.map((s) => s.category)).toEqual(['fitness', 'sleep']);
    expect(shares[0].share).toBeCloseTo(0.75);
    expect(percent(0.666)).toBe('67%');
  });
});
