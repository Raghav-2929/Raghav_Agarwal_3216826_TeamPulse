/**
 * Verifies the integration contract between Svelte 5 and the Stencil custom elements:
 *  1. the elements register in a DOM and render into their shadow roots,
 *  2. Svelte sets array props as DOM properties (not "[object Object]" attributes),
 *  3. dash-cased custom events are received through Svelte 5 `ontp-…` event attributes.
 */
import { flushSync, mount, tick, unmount } from 'svelte';
import { describe, expect, it, vi } from 'vitest';
import { registerUiComponents } from './register';
import EventProbe from './EventProbe.test-fixture.svelte';

async function settle(predicate: () => boolean, timeoutMs = 2000) {
  const start = Date.now();
  while (!predicate()) {
    if (Date.now() - start > timeoutMs) throw new Error('timed out waiting for custom element render');
    await new Promise((r) => setTimeout(r, 10));
  }
}

describe('Svelte 5 ↔ @teampulse/ui-components', () => {
  it('passes arrays as properties and receives tp-* events via on… attributes', async () => {
    await registerUiComponents();
    expect(customElements.get('tp-leaderboard-table')).toBeDefined();

    const onrow = vi.fn();
    const onaction = vi.fn();
    const rows = [
      { rank: 1, display_name: 'Alice Johnson', team_name: 'Engineering', score: 12, is_me: false },
      { rank: 2, display_name: 'Ben Carter', team_name: 'Engineering', score: 9, is_me: true },
    ];
    const target = document.createElement('div');
    document.body.appendChild(target);
    const app = mount(EventProbe, { target, props: { rows, onrow, onaction } });
    flushSync();
    await tick();

    const table = target.querySelector('tp-leaderboard-table') as HTMLElement & { entries: unknown };
    // Set as a property, so the element holds the very same array instance.
    expect(table.entries).toBe(rows);
    expect(table.hasAttribute('entries')).toBe(false);

    await settle(() => (table.shadowRoot?.querySelectorAll('tbody tr[data-index]').length ?? 0) === 2);
    const rowEls = table.shadowRoot!.querySelectorAll<HTMLElement>('tbody tr[data-index]');
    expect(rowEls[1].classList.contains('me')).toBe(true);

    rowEls[1].click();
    expect(onrow).toHaveBeenCalledTimes(1);
    expect(onrow.mock.calls[0][0]).toMatchObject({ index: 1, mode: 'individual', entry: rows[1] });

    const card = target.querySelector('tp-progress-card') as HTMLElement;
    await settle(() => !!card.shadowRoot?.querySelector('button'));
    card.shadowRoot!.querySelector<HTMLButtonElement>('button')!.click();
    expect(onaction).toHaveBeenCalledWith({ action: 'complete' });

    unmount(app);
    target.remove();
  });
});
