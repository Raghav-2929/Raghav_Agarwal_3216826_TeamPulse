import { newSpecPage } from '@stencil/core/testing';
import { TpTrendChart } from '../tp-trend-chart';

const series = [
  {
    label: 'Completions',
    points: [
      { x: '2026-11-01', y: 9 },
      { x: '2026-11-02', y: null },
      { x: '2026-11-03', y: 7 },
      { x: '2026-11-04', y: 11 },
    ],
  },
];

describe('tp-trend-chart', () => {
  it('renders an empty state without data', async () => {
    const page = await newSpecPage({ components: [TpTrendChart], html: `<tp-trend-chart empty-text="Nothing yet"></tp-trend-chart>` });
    expect(page.root!.shadowRoot!.querySelector('.empty')!.textContent).toBe('Nothing yet');
    expect(page.root!.shadowRoot!.querySelector('svg')).toBeNull();
  });

  it('breaks the line at null points and marks the gap', async () => {
    const page = await newSpecPage({ components: [TpTrendChart], html: `<tp-trend-chart label="Team trend"></tp-trend-chart>` });
    page.root!.series = series;
    await page.waitForChanges();
    const root = page.root!.shadowRoot!;
    // [9] | gap | [7, 11] → one isolated dot + one 2-point path
    expect(root.querySelectorAll('path.line').length).toBe(1);
    expect(root.querySelectorAll('rect.gap').length).toBe(1);
    expect(root.querySelectorAll('rect.hit').length).toBe(4);
    expect(root.querySelector('svg')!.getAttribute('aria-label')).toBe('Team trend');
  });

  it('accepts JSON via attribute and renders bars, skipping nulls', async () => {
    const page = await newSpecPage({
      components: [TpTrendChart],
      html: `<tp-trend-chart type="bar" series='${JSON.stringify(series)}'></tp-trend-chart>`,
    });
    expect(page.root!.shadowRoot!.querySelectorAll('rect.bar').length).toBe(3);
  });

  it('uses the gap label in the accessible table and aria labels', async () => {
    const page = await newSpecPage({
      components: [TpTrendChart],
      html: `<tp-trend-chart gap-label="Suppressed (fewer than 3 members)"></tp-trend-chart>`,
    });
    page.root!.series = series;
    await page.waitForChanges();
    const root = page.root!.shadowRoot!;
    const cells = Array.from(root.querySelectorAll('table.sr-only tbody td')).map((td) => td.textContent);
    expect(cells).toEqual(['9', 'Suppressed (fewer than 3 members)', '7', '11']);
    expect(root.querySelector('[data-hit="1"]')!.getAttribute('aria-label')).toBe('Nov 2, 2026. Completions: Suppressed (fewer than 3 members)');
    expect(root.querySelector('.legend-gap')!.textContent).toContain('Suppressed');
  });

  it('shows a tooltip on focus and uses a roving tabindex', async () => {
    const page = await newSpecPage({ components: [TpTrendChart], html: `<tp-trend-chart></tp-trend-chart>` });
    page.root!.series = series;
    await page.waitForChanges();
    const root = page.root!.shadowRoot!;
    expect(root.querySelector('[data-hit="0"]')!.getAttribute('tabindex')).toBe('0');
    expect(root.querySelector('[data-hit="2"]')!.getAttribute('tabindex')).toBe('-1');

    root.querySelector('[data-hit="2"]')!.dispatchEvent(new Event('focus'));
    await page.waitForChanges();
    const tooltip = root.querySelector('.tooltip')!;
    expect(tooltip.textContent).toContain('Nov 3, 2026');
    expect(tooltip.textContent).toContain('7');
    expect(root.querySelector('[data-hit="2"]')!.getAttribute('tabindex')).toBe('0');
  });

  it('emits tp-point-select on click and Enter', async () => {
    const page = await newSpecPage({ components: [TpTrendChart], html: `<tp-trend-chart></tp-trend-chart>` });
    page.root!.series = series;
    await page.waitForChanges();
    const spy = jest.fn();
    page.root!.addEventListener('tp-point-select', spy);
    const hit = page.root!.shadowRoot!.querySelector('[data-hit="3"]')!;
    hit.dispatchEvent(new MouseEvent('click'));
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0].detail).toEqual({ index: 3, x: '2026-11-04', values: [{ label: 'Completions', y: 11 }] });

    hit.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(spy).toHaveBeenCalledTimes(2);
  });

  it('renders a legend entry per series', async () => {
    const page = await newSpecPage({ components: [TpTrendChart], html: `<tp-trend-chart></tp-trend-chart>` });
    page.root!.series = [series[0], { label: 'Active members', color: 'red', points: [{ x: '2026-11-01', y: 4 }] }];
    await page.waitForChanges();
    const items = Array.from(page.root!.shadowRoot!.querySelectorAll('.legend li')).map((li) => li.textContent!.trim());
    expect(items).toEqual(['Completions', 'Active members', 'No data']);
  });
});
