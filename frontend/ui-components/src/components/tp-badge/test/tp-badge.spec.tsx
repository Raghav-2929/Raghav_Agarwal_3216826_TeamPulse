import { newSpecPage } from '@stencil/core/testing';
import { TpBadge } from '../tp-badge';

describe('tp-badge', () => {
  it('renders an earned badge with its award date', async () => {
    const page = await newSpecPage({
      components: [TpBadge],
      html: `<tp-badge icon="🔥" name="Week Warrior" description="7-day streak" awarded-at="2026-11-08T12:00:00Z"></tp-badge>`,
    });
    const root = page.root!.shadowRoot!;
    expect(root.querySelector('.icon')!.textContent).toBe('🔥');
    expect(root.querySelector('.name')!.textContent).toBe('Week Warrior');
    expect(root.querySelector('.meta')!.textContent).toBe('Earned Nov 8, 2026');
    expect(root.querySelector('figure')!.getAttribute('aria-label')).toBe('Week Warrior badge. Earned Nov 8, 2026. 7-day streak');
    expect(root.querySelector('.lock')).toBeNull();
  });

  it('renders a locked badge', async () => {
    const page = await newSpecPage({ components: [TpBadge], html: `<tp-badge name="Century" locked></tp-badge>` });
    const root = page.root!.shadowRoot!;
    expect(root.querySelector('figure')!.classList.contains('locked')).toBe(true);
    expect(root.querySelector('.lock')).not.toBeNull();
    expect(root.querySelector('.meta')!.textContent).toBe('Locked');
  });

  it('supports a compact layout', async () => {
    const page = await newSpecPage({ components: [TpBadge], html: `<tp-badge name="Hydrated" description="x" compact></tp-badge>` });
    expect(page.root!.shadowRoot!.querySelector('.description')).toBeNull();
  });
});
