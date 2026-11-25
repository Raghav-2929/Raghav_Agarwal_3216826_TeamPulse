import { Component, Element, Event, EventEmitter, Host, Prop, State, h } from '@stencil/core';
import type { LeaderboardEntry, LeaderboardMode, LeaderboardRowSelectDetail, TeamLeaderboardEntry } from '../../types';
import { parseArrayProp } from '../../utils/parse';
import { formatNumber } from '../../utils/format';

const MEDALS: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };

/**
 * Ranked leaderboard for challenges, in individual or team mode.
 * Rows are keyboard-navigable (↑/↓/Home/End) and selectable (click, Enter, Space).
 *
 * @slot caption - Heading content rendered above the table (e.g. a title).
 * @slot actions - Controls rendered at the end of the header bar (e.g. a mode switch).
 * @part table - The `<table>` element.
 * @part row - Each body row.
 */
@Component({
  tag: 'tp-leaderboard-table',
  styleUrl: 'tp-leaderboard-table.css',
  shadow: true,
})
export class TpLeaderboardTable {
  @Element() el!: HTMLElement;

  /**
   * Rows to render. Accepts an array (set as a JS property) or a JSON string (attribute).
   * Individual rows: `{rank, display_name, team_name?, score, goal_reached?, is_me?}`.
   * Team rows: `{rank, team_name, participants, total_score, average_score}`.
   */
  @Prop() entries: LeaderboardEntry[] | TeamLeaderboardEntry[] | string = [];

  /** `individual` or `team`. */
  @Prop() mode: LeaderboardMode = 'individual';

  /** Highlights the row flagged `is_me` (individual mode). */
  @Prop() highlightMe: boolean = true;

  /** Message shown when there are no rows. */
  @Prop() emptyText: string = 'No participants yet.';

  /** Accessible caption for the table (visually hidden). */
  @Prop() caption: string = 'Leaderboard';

  /** Header of the score column in individual mode. */
  @Prop() scoreLabel: string = 'Score';

  /**
   * Emitted when a row is activated by click, Enter or Space.
   * Listen in Svelte 5 with `ontp-row-select={(e) => …}`.
   */
  @Event({ eventName: 'tp-row-select', bubbles: true, composed: true })
  rowSelect!: EventEmitter<LeaderboardRowSelectDetail>;

  /** Bumped when slotted header content is added or removed later, so the header is shown again. */
  @State() private slotVersion = 0;

  private onSlotChange = () => {
    this.slotVersion++;
  };

  private select(index: number, entry: LeaderboardEntry | TeamLeaderboardEntry) {
    this.rowSelect.emit({ index, mode: this.mode === 'team' ? 'team' : 'individual', entry });
  }

  private onRowKeyDown(event: KeyboardEvent, index: number, entry: LeaderboardEntry | TeamLeaderboardEntry) {
    const rows = Array.from(this.el.shadowRoot?.querySelectorAll<HTMLTableRowElement>('tbody tr[data-index]') ?? []);
    let target: number | null = null;
    switch (event.key) {
      case 'Enter':
      case ' ':
        event.preventDefault();
        this.select(index, entry);
        return;
      case 'ArrowDown':
        target = Math.min(rows.length - 1, index + 1);
        break;
      case 'ArrowUp':
        target = Math.max(0, index - 1);
        break;
      case 'Home':
        target = 0;
        break;
      case 'End':
        target = rows.length - 1;
        break;
      default:
        return;
    }
    event.preventDefault();
    rows[target]?.focus();
  }

  private renderRank(rank: number) {
    const medal = MEDALS[rank];
    return (
      <td class="rank">
        {medal ? (
          <span class="medal" data-rank={rank}>
            <span aria-hidden="true">{medal}</span>
            <span class="sr-only">{rank}</span>
          </span>
        ) : (
          <span class="rank-number">{rank}</span>
        )}
      </td>
    );
  }

  private renderIndividual(rows: LeaderboardEntry[]) {
    return [
      <thead>
        <tr>
          <th scope="col" class="rank">
            Rank
          </th>
          <th scope="col">Participant</th>
          <th scope="col" class="col-team">
            Team
          </th>
          <th scope="col" class="num">
            {this.scoreLabel}
          </th>
          <th scope="col" class="goal">
            Goal
          </th>
        </tr>
      </thead>,
      <tbody>
        {rows.map((row, index) => {
          const isMe = this.highlightMe && !!row.is_me;
          return (
            <tr
              key={`${row.rank}-${row.display_name}-${index}`}
              part="row"
              data-index={index}
              tabIndex={0}
              class={{ me: isMe, podium: row.rank <= 3 }}
              aria-current={isMe ? 'true' : undefined}
              onClick={() => this.select(index, row)}
              onKeyDown={(ev: KeyboardEvent) => this.onRowKeyDown(ev, index, row)}
            >
              {this.renderRank(row.rank)}
              <td class="name">
                <span class="name-text">{row.display_name}</span>
                {isMe && <span class="you">You</span>}
              </td>
              <td class="col-team">{row.team_name ?? '—'}</td>
              <td class="num score">{formatNumber(row.score)}</td>
              <td class="goal">
                {row.goal_reached ? (
                  <span class="goal-yes" title="Goal reached">
                    <span aria-hidden="true">✓</span>
                    <span class="sr-only">Goal reached</span>
                  </span>
                ) : (
                  <span class="goal-no">
                    <span aria-hidden="true">–</span>
                    <span class="sr-only">Not yet</span>
                  </span>
                )}
              </td>
            </tr>
          );
        })}
      </tbody>,
    ];
  }

  private renderTeams(rows: TeamLeaderboardEntry[]) {
    return [
      <thead>
        <tr>
          <th scope="col" class="rank">
            Rank
          </th>
          <th scope="col">Team</th>
          <th scope="col" class="num">
            Participants
          </th>
          <th scope="col" class="num">
            Total
          </th>
          <th scope="col" class="num col-avg">
            Average
          </th>
        </tr>
      </thead>,
      <tbody>
        {rows.map((row, index) => (
          <tr
            key={`${row.rank}-${row.team_name}-${index}`}
            part="row"
            data-index={index}
            tabIndex={0}
            class={{ podium: row.rank <= 3 }}
            onClick={() => this.select(index, row)}
            onKeyDown={(ev: KeyboardEvent) => this.onRowKeyDown(ev, index, row)}
          >
            {this.renderRank(row.rank)}
            <td class="name">
              <span class="name-text">{row.team_name}</span>
            </td>
            <td class="num">{formatNumber(row.participants)}</td>
            <td class="num score">{formatNumber(row.total_score)}</td>
            <td class="num col-avg">{formatNumber(row.average_score)}</td>
          </tr>
        ))}
      </tbody>,
    ];
  }

  render() {
    const isTeam = this.mode === 'team';
    const rows = parseArrayProp<LeaderboardEntry | TeamLeaderboardEntry>(this.entries);
    const columns = 5;
    const hasHeader = !!this.el.querySelector('[slot="caption"], [slot="actions"]');

    return (
      <Host>
        <div class="wrapper">
          <div class={{ header: true, hidden: !hasHeader }}>
            <div class="caption-slot">
              <slot name="caption" onSlotchange={this.onSlotChange} />
            </div>
            <div class="actions-slot">
              <slot name="actions" onSlotchange={this.onSlotChange} />
            </div>
          </div>
          <div class="scroller">
            <table part="table" class={{ team: isTeam }}>
              <caption class="sr-only">{this.caption}</caption>
              {rows.length === 0 ? (
                <tbody>
                  <tr class="empty">
                    <td colSpan={columns}>{this.emptyText}</td>
                  </tr>
                </tbody>
              ) : isTeam ? (
                this.renderTeams(rows as TeamLeaderboardEntry[])
              ) : (
                this.renderIndividual(rows as LeaderboardEntry[])
              )}
            </table>
          </div>
        </div>
      </Host>
    );
  }
}
