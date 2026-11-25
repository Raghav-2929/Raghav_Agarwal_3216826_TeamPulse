import { clamp, parseArrayProp, percentOf, toNumber } from './parse';
import { categoryIcon, categoryLabel, deltaTrend, formatDelta, formatLongDate, formatNumber, formatShortDate, toneColor } from './format';
import { allIntegers, alignSeries, collectXValues, labelStride, lineSegments, maxValue, niceMax, niceScale, yTicks } from './chart';

describe('parseArrayProp', () => {
  it('passes arrays through', () => {
    const arr = [{ a: 1 }];
    expect(parseArrayProp(arr)).toBe(arr);
  });
  it('parses JSON strings', () => {
    expect(parseArrayProp('[1,2,3]')).toEqual([1, 2, 3]);
  });
  it('returns [] for invalid JSON, non-arrays and empty values', () => {
    expect(parseArrayProp('{not json')).toEqual([]);
    expect(parseArrayProp('{"a":1}')).toEqual([]);
    expect(parseArrayProp('')).toEqual([]);
    expect(parseArrayProp(undefined)).toEqual([]);
    expect(parseArrayProp(null)).toEqual([]);
  });
});

describe('numeric helpers', () => {
  it('toNumber coerces numeric strings and falls back', () => {
    expect(toNumber('12')).toBe(12);
    expect(toNumber(3.5)).toBe(3.5);
    expect(toNumber('abc', 7)).toBe(7);
    expect(toNumber('', 2)).toBe(2);
  });
  it('clamp and percentOf stay within bounds', () => {
    expect(clamp(150, 0, 100)).toBe(100);
    expect(percentOf(3, 4)).toBe(75);
    expect(percentOf(10, 4)).toBe(100);
    expect(percentOf(1, 0)).toBe(0);
    expect(percentOf(-2, 10)).toBe(0);
  });
});

describe('format helpers', () => {
  it('formats ISO dates without timezone drift', () => {
    expect(formatShortDate('2026-11-08')).toBe('Nov 8');
    expect(formatShortDate('Engineering')).toBe('Engineering');
    expect(formatLongDate('2026-01-31T12:00:00Z')).toBe('Jan 31, 2026');
    expect(formatLongDate('2026-01-31')).toBe('Jan 31, 2026');
    expect(formatLongDate('')).toBe('');
  });
  it('formats numbers', () => {
    expect(formatNumber(1200)).toBe('1,200');
    expect(formatNumber(7.756)).toBe('7.76');
    expect(formatNumber(null)).toBe('–');
  });
  it('maps tones and categories to tokens', () => {
    expect(toneColor('fitness')).toBe('var(--tp-color-category-fitness)');
    expect(toneColor('success')).toBe('var(--tp-color-success)');
    expect(toneColor(undefined)).toBe('var(--tp-color-primary)');
    expect(categoryIcon('sleep')).toBe('😴');
    expect(categoryIcon('unknown')).toBe('⭐');
    expect(categoryLabel('hydration')).toBe('Hydration');
  });
  it('derives delta direction from numbers and strings', () => {
    expect(deltaTrend(3)).toBe('up');
    expect(deltaTrend(-1)).toBe('down');
    expect(deltaTrend(0)).toBe('flat');
    expect(deltaTrend('+12%')).toBe('up');
    expect(deltaTrend('−4')).toBe('down');
    expect(deltaTrend('')).toBeNull();
    expect(formatDelta(3)).toBe('+3');
    expect(formatDelta(-2)).toBe('-2');
    expect(formatDelta('+5%')).toBe('+5%');
    expect(formatDelta('12')).toBe('+12'); // attribute text that is a plain number
    expect(formatDelta('-3')).toBe('-3');
    expect(formatDelta('0')).toBe('0');
  });
});

describe('chart helpers', () => {
  const series = [
    {
      label: 'A',
      points: [
        { x: '2026-11-03', y: 3 },
        { x: '2026-11-01', y: 1 },
      ],
    },
    {
      label: 'B',
      points: [
        { x: '2026-11-02', y: null },
        { x: '2026-11-01', y: 5 },
      ],
    },
  ];

  it('collects and sorts the shared x domain', () => {
    expect(collectXValues(series)).toEqual(['2026-11-01', '2026-11-02', '2026-11-03']);
    expect(
      collectXValues([
        {
          label: 'c',
          points: [
            { x: 'Ops', y: 1 },
            { x: 'Eng', y: 2 },
          ],
        },
      ]),
    ).toEqual(['Ops', 'Eng']);
  });

  it('aligns series with nulls for missing or suppressed points', () => {
    const xs = collectXValues(series);
    expect(alignSeries(series[0], xs)).toEqual([1, null, 3]);
    expect(alignSeries(series[1], xs)).toEqual([5, null, null]);
    expect(maxValue([alignSeries(series[0], xs), alignSeries(series[1], xs)])).toBe(5);
  });

  it('computes nice axis maxima and ticks', () => {
    expect(niceMax(0)).toBe(1);
    expect(niceMax(7)).toBe(10);
    expect(niceMax(13)).toBe(20);
    expect(niceMax(23)).toBe(25);
    expect(niceMax(0.3)).toBe(1);
    expect(yTicks(20, 4)).toEqual([0, 5, 10, 15, 20]);
  });

  it('builds readable integer scales for count data', () => {
    expect(niceScale(5)).toEqual({ max: 6, step: 2, ticks: [0, 2, 4, 6] });
    expect(niceScale(11).ticks).toEqual([0, 5, 10, 15]);
    expect(niceScale(226).ticks).toEqual([0, 100, 200, 300]);
    expect(niceScale(0)).toEqual({ max: 4, step: 1, ticks: [0, 1, 2, 3, 4] });
    expect(niceScale(3).ticks).toEqual([0, 1, 2, 3]);
  });

  it('allows fractional steps for non-integer data', () => {
    expect(niceScale(0.75, { integer: false }).ticks).toEqual([0, 0.2, 0.4, 0.6, 0.8]);
    expect(allIntegers([[1, null, 3]])).toBe(true);
    expect(allIntegers([[1.5]])).toBe(false);
  });

  it('breaks lines at null values', () => {
    const segs = lineSegments([1, 2, null, 3, null, 4, 5], (i) => i * 10, (v) => 100 - v);
    expect(segs).toHaveLength(3);
    expect(segs[0]).toEqual({ d: 'M0,99 L10,98', points: 2 });
    expect(segs[1]).toEqual({ d: 'M30,97', points: 1 });
    expect(segs[2].points).toBe(2);
  });

  it('limits the number of x labels', () => {
    expect(labelStride(30, 7)).toBe(5);
    expect(labelStride(5, 10)).toBe(1);
    expect(labelStride(0, 10)).toBe(1);
  });
});
