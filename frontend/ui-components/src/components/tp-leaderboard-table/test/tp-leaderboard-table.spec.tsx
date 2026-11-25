import { newSpecPage } from '@stencil/core/testing';
import { TpLeaderboardTable } from '../tp-leaderboard-table';

const individuals = [
  { rank: 1, display_name: 'Alice Johnson', team_name: 'Engineering', score: 12, goal_reached: true, is_me: false },
  { rank: 2, display_name: 'Ben Carter', team_name: 'Engineering', score: 9, goal_reached: false, is_me: true },
  { rank: 4, display_name: 'Anonymous participant', team_name: 'Marketing', score: 3 },
];

const teams = [
  { rank: 1, team_id: 't1', team_name: 'Engineering', participants: 4, total_score: 31, average_score: 7.75 },
  { rank: 2, team_id: 't2', team_name: 'Marketing', participants: 3, total_score: 12, average_score: 4 },
];

describe('tp-leaderboard-table', () => {
  it('renders individual rows from a JS array and highlights me', async () => {
    const page = await newSpecPage({ components: [TpLeaderboardTable], html: `<tp-leaderboard-table></tp-leaderboard-table>` });
    page.root!.entries = individuals;
    await page.waitForChanges();
    const rows = page.root!.shadowRoot!.querySelectorAll('tbody tr');
    expect(rows.length).toBe(3);
    expect(rows[0].querySelector('.name-text')!.textContent).toBe('Alice Johnson');
    expect(rows[0].querySelector('.medal')).not.toBeNull();
    expect(rows[2].querySelector('.rank-number')!.textContent).toBe('4');
    expect(rows[1].classList.contains('me')).toBe(true);
    expect(rows[1].getAttribute('aria-current')).toBe('true');
    expect(rows[1].querySelector('.you')!.textContent).toBe('You');
    expect(rows[0].querySelector('.goal-yes')).not.toBeNull();
  });

  it('accepts a JSON string attribute', async () => {
    const page = await newSpecPage({
      components: [TpLeaderboardTable],
      html: `<tp-leaderboard-table entries='${JSON.stringify(individuals.slice(0, 1))}'></tp-leaderboard-table>`,
    });
    expect(page.root!.shadowRoot!.querySelectorAll('tbody tr[data-index]').length).toBe(1);
  });

  it('does not highlight me when highlight-me is false', async () => {
    const page = await newSpecPage({ components: [TpLeaderboardTable], html: `<tp-leaderboard-table highlight-me="false"></tp-leaderboard-table>` });
    page.root!.entries = individuals;
    await page.waitForChanges();
    expect(page.root!.shadowRoot!.querySelector('tr.me')).toBeNull();
  });

  it('renders team mode columns', async () => {
    const page = await newSpecPage({ components: [TpLeaderboardTable], html: `<tp-leaderboard-table mode="team"></tp-leaderboard-table>` });
    page.root!.entries = teams;
    await page.waitForChanges();
    const headers = Array.from(page.root!.shadowRoot!.querySelectorAll('th')).map((th) => th.textContent!.trim());
    expect(headers).toEqual(['Rank', 'Team', 'Participants', 'Total', 'Average']);
    const firstRow = page.root!.shadowRoot!.querySelector('tbody tr')!;
    expect(firstRow.textContent).toContain('7.75');
  });

  it('shows the empty text when there are no entries', async () => {
    const page = await newSpecPage({
      components: [TpLeaderboardTable],
      html: `<tp-leaderboard-table empty-text="Be the first to join!"></tp-leaderboard-table>`,
    });
    expect(page.root!.shadowRoot!.querySelector('tr.empty')!.textContent).toBe('Be the first to join!');
  });

  it('emits tp-row-select on click and on Enter', async () => {
    const page = await newSpecPage({ components: [TpLeaderboardTable], html: `<tp-leaderboard-table></tp-leaderboard-table>` });
    page.root!.entries = individuals;
    await page.waitForChanges();
    const spy = jest.fn();
    page.root!.addEventListener('tp-row-select', spy);
    const rows = page.root!.shadowRoot!.querySelectorAll<HTMLElement>('tbody tr');

    rows[1].click();
    expect(spy).toHaveBeenCalledTimes(1);
    expect(spy.mock.calls[0][0].detail).toEqual({ index: 1, mode: 'individual', entry: individuals[1] });

    rows[2].dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }));
    expect(spy).toHaveBeenCalledTimes(2);
    expect(spy.mock.calls[1][0].detail.index).toBe(2);
  });

  it('shows header slots only when content is provided', async () => {
    const page = await newSpecPage({
      components: [TpLeaderboardTable],
      html: `<tp-leaderboard-table><strong slot="caption">Top movers</strong></tp-leaderboard-table>`,
    });
    expect(page.root!.shadowRoot!.querySelector('.header')!.classList.contains('hidden')).toBe(false);
    const bare = await newSpecPage({ components: [TpLeaderboardTable], html: `<tp-leaderboard-table></tp-leaderboard-table>` });
    expect(bare.root!.shadowRoot!.querySelector('.header')!.classList.contains('hidden')).toBe(true);
  });

  it('shows the header when caption content is added after the first render', async () => {
    const page = await newSpecPage({ components: [TpLeaderboardTable], html: `<tp-leaderboard-table></tp-leaderboard-table>` });
    const header = () => page.root!.shadowRoot!.querySelector('.header')!;
    expect(header().classList.contains('hidden')).toBe(true);
    const caption = page.doc.createElement('strong');
    caption.setAttribute('slot', 'caption');
    caption.textContent = 'Top movers';
    page.root!.appendChild(caption);
    page.root!.shadowRoot!.querySelector('slot[name="caption"]')!.dispatchEvent(new Event('slotchange'));
    await page.waitForChanges();
    expect(header().classList.contains('hidden')).toBe(false);
  });
});
