import { describe, expect, it } from 'vitest';
import {
  addDays,
  detectPreset,
  diffDays,
  enumerateDays,
  formatDate,
  formatRange,
  isValidISODate,
  presetRange,
  relativeTime,
  toISODate,
  validateRange,
} from './dates';

describe('date arithmetic', () => {
  it('formats local dates without UTC drift', () => {
    expect(toISODate(new Date(2026, 10, 8, 23, 59))).toBe('2026-11-08');
    expect(toISODate(new Date(2026, 0, 1, 0, 1))).toBe('2026-01-01');
  });

  it('adds days across month, year and DST boundaries', () => {
    expect(addDays('2026-11-08', -13)).toBe('2026-10-26');
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01');
    expect(addDays('2026-03-28', 2)).toBe('2026-03-30');
    expect(addDays('2028-02-28', 1)).toBe('2028-02-29');
  });

  it('computes differences and enumerates inclusive ranges', () => {
    expect(diffDays('2026-11-01', '2026-11-08')).toBe(7);
    expect(diffDays('2026-11-08', '2026-11-01')).toBe(-7);
    expect(enumerateDays('2026-10-30', '2026-11-02')).toEqual(['2026-10-30', '2026-10-31', '2026-11-01', '2026-11-02']);
    expect(enumerateDays('2026-11-02', '2026-11-01')).toEqual([]);
  });

  it('validates ISO dates strictly', () => {
    expect(isValidISODate('2026-11-08')).toBe(true);
    expect(isValidISODate('2026-02-30')).toBe(false);
    expect(isValidISODate('2026-1-8')).toBe(false);
    expect(isValidISODate(undefined)).toBe(false);
  });
});

describe('range presets', () => {
  const today = '2026-11-08';

  it('builds "last N days" ranges that include today', () => {
    expect(presetRange('7d', today)).toEqual({ from: '2026-11-02', to: today });
    expect(presetRange('14d', today)).toEqual({ from: '2026-10-26', to: today });
    expect(presetRange('30d', today)).toEqual({ from: '2026-10-10', to: today });
    expect(presetRange('180d', today)).toEqual({ from: addDays(today, -179), to: today });
  });

  it('detects which preset a range matches', () => {
    expect(detectPreset({ from: '2026-11-02', to: today }, today)).toBe('7d');
    expect(detectPreset(presetRange('90d', today), today)).toBe('90d');
    expect(detectPreset({ from: '2026-11-01', to: today }, today)).toBe('custom');
    expect(detectPreset({ from: '', to: today }, today)).toBe('custom');
  });

  it('validates ranges against the 180-day API limit', () => {
    expect(validateRange({ from: '2026-11-01', to: today }, { today })).toBeNull();
    expect(validateRange({ from: today, to: '2026-11-01' }, { today })).toMatch(/on or before/);
    expect(validateRange({ from: '2026-01-01', to: today }, { today })).toMatch(/at most 180 days/);
    expect(validateRange({ from: '2026-11-01', to: '2026-11-09' }, { today })).toMatch(/future/);
    expect(validateRange({ from: '2026-11-01', to: '2026-11-09' }, { today, allowFuture: true })).toBeNull();
    expect(validateRange({}, { today })).toMatch(/Choose/);
    expect(validateRange({}, { today, required: false })).toBeNull();
    expect(validateRange({ from: 'nope', to: today }, { today })).toMatch(/not a valid date/);
  });
});

describe('formatting', () => {
  it('formats dates and ranges', () => {
    expect(formatDate('2026-11-08')).toBe('Nov 8, 2026');
    expect(formatDate('2026-11-08T12:00:00Z')).toBe('Nov 8, 2026');
    expect(formatDate(new Date(2026, 10, 8, 23, 30).toISOString())).toBe('Nov 8, 2026'); // local calendar day
    expect(formatDate(null)).toBe('');
    expect(formatRange({ from: '2026-11-01', to: '2026-11-08' })).toBe('Nov 1 – Nov 8, 2026');
    expect(formatRange({ from: '2025-12-30', to: '2026-01-02' })).toBe('Dec 30, 2025 – Jan 2, 2026');
  });

  it('describes relative times', () => {
    const now = new Date('2026-11-08T12:00:00Z');
    expect(relativeTime('2026-11-08T11:59:40Z', now)).toBe('just now');
    expect(relativeTime('2026-11-08T11:30:00Z', now)).toBe('30 min ago');
    expect(relativeTime('2026-11-08T09:00:00Z', now)).toBe('3 h ago');
    expect(relativeTime('2026-11-06T12:00:00Z', now)).toBe('2 d ago');
  });
});
