import { newSpecPage } from '@stencil/core/testing';
import { TpProgressRing } from '../tp-progress-ring';

describe('tp-progress-ring', () => {
  it('exposes progressbar semantics', async () => {
    const page = await newSpecPage({
      components: [TpProgressRing],
      html: `<tp-progress-ring value="3" max="4" label="Habits today"></tp-progress-ring>`,
    });
    const ring = page.root!.shadowRoot!.querySelector('[role="progressbar"]')!;
    expect(ring.getAttribute('aria-label')).toBe('Habits today');
    expect(ring.getAttribute('aria-valuenow')).toBe('3');
    expect(ring.getAttribute('aria-valuemax')).toBe('4');
    expect(ring.getAttribute('aria-valuetext')).toBe('3 of 4 (75%)');
    expect(page.root!.shadowRoot!.querySelector('.pct')!.textContent).toBe('75%');
  });

  it('clamps overflow and handles a zero max', async () => {
    const page = await newSpecPage({
      components: [TpProgressRing],
      html: `<tp-progress-ring value="12" max="10"></tp-progress-ring>`,
    });
    expect(page.root!.shadowRoot!.querySelector('.pct')!.textContent).toBe('100%');
    expect(page.root!.shadowRoot!.querySelector('[role="progressbar"]')!.getAttribute('aria-valuenow')).toBe('10');

    page.root!.max = 0;
    await page.waitForChanges();
    expect(page.root!.shadowRoot!.querySelector('.pct')!.textContent).toBe('0%');
  });

  it('sizes the svg and colours the indicator from the tone', async () => {
    const page = await newSpecPage({
      components: [TpProgressRing],
      html: `<tp-progress-ring value="1" max="2" size="80" stroke-width="6" tone="sleep"></tp-progress-ring>`,
    });
    const svg = page.root!.shadowRoot!.querySelector('svg')!;
    expect(svg.getAttribute('width')).toBe('80');
    const indicator = page.root!.shadowRoot!.querySelector('.indicator')!;
    expect(indicator.getAttribute('stroke')).toBe('var(--tp-color-category-sleep)');
    expect(indicator.getAttribute('stroke-width')).toBe('6');
  });

  it('renders slotted centre content instead of the percentage', async () => {
    const page = await newSpecPage({
      components: [TpProgressRing],
      html: `<tp-progress-ring value="5" max="20"><strong>5/20</strong></tp-progress-ring>`,
    });
    expect(page.root!.querySelector('strong')!.textContent).toBe('5/20');
    expect(page.root!.shadowRoot!.querySelector('slot')).not.toBeNull();
  });
});
