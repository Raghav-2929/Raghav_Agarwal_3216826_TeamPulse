import { newSpecPage } from '@stencil/core/testing';
import { TpStatTile } from '../tp-stat-tile';

describe('tp-stat-tile', () => {
  it('renders label, value and hint', async () => {
    const page = await newSpecPage({
      components: [TpStatTile],
      html: `<tp-stat-tile label="Completions" value="42" hint="last 30 days"></tp-stat-tile>`,
    });
    const root = page.root!.shadowRoot!;
    expect(root.querySelector('.label')!.textContent).toBe('Completions');
    expect(root.querySelector('.value')!.textContent).toBe('42');
    expect(root.querySelector('.hint')!.textContent).toBe('last 30 days');
    expect(root.querySelector('.delta')).toBeNull();
  });

  it('shows a positive delta as good', async () => {
    const page = await newSpecPage({ components: [TpStatTile], html: `<tp-stat-tile label="x" value="1" delta="+12%"></tp-stat-tile>` });
    const delta = page.root!.shadowRoot!.querySelector('.delta')!;
    expect(delta.classList.contains('good')).toBe(true);
    expect(delta.textContent).toContain('+12%');
    expect(delta.textContent).toContain('Increased by');
  });

  it('gives a plain-number delta attribute the same plus sign as a number', async () => {
    const page = await newSpecPage({ components: [TpStatTile], html: `<tp-stat-tile label="x" value="1" delta="12"></tp-stat-tile>` });
    const delta = page.root!.shadowRoot!.querySelector('.delta')!;
    expect(delta.textContent).toContain('+12');
  });

  it('inverts colouring when a decrease is good', async () => {
    const page = await newSpecPage({ components: [TpStatTile], html: `<tp-stat-tile label="Suppressed days" value="2" invert-delta></tp-stat-tile>` });
    page.root!.delta = -3;
    await page.waitForChanges();
    const delta = page.root!.shadowRoot!.querySelector('.delta')!;
    expect(delta.classList.contains('good')).toBe(true);
    expect(delta.textContent).toContain('-3');
  });

  it('renders a dash for an empty value', async () => {
    const page = await newSpecPage({ components: [TpStatTile], html: `<tp-stat-tile label="x"></tp-stat-tile>` });
    expect(page.root!.shadowRoot!.querySelector('.value')!.textContent).toBe('–');
  });
});
