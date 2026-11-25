import { Component, Element, Event, EventEmitter, Host, Prop, State, h } from '@stencil/core';
import type { ProgressCardActionDetail } from '../../types';
import { percentOf, toNumber } from '../../utils/parse';
import { categoryIcon, categoryLabel, formatNumber, isCategory, toneColor } from '../../utils/format';

/**
 * Card summarising progress on a habit, streak or goal, with an optional built-in action
 * button (e.g. "Mark complete").
 *
 * @slot - Extra body content rendered under the heading.
 * @slot icon - Leading icon. Defaults to the category emoji.
 * @slot actions - Additional action controls rendered in the footer (before the built-in button).
 * @part card - The card container.
 * @part action - The built-in action button.
 */
@Component({
  tag: 'tp-progress-card',
  styleUrl: 'tp-progress-card.css',
  shadow: true,
})
export class TpProgressCard {
  @Element() el!: HTMLElement;

  /** Card title (named `heading` because `title` is a reserved global attribute). */
  @Prop() heading: string = '';

  /** Current progress value. */
  @Prop() value: number = 0;

  /** Target value; when `0` no progress meter is shown. */
  @Prop() target: number = 0;

  /** Unit shown after the figures (e.g. `days`, `check-ins`). */
  @Prop() unit: string = '';

  /** Current streak length; hidden when `0`. */
  @Prop() streak: number = 0;

  /** Unit of the streak (`day` or `week`). */
  @Prop() streakUnit: string = 'day';

  /** Activity type; drives the accent colour and default icon. */
  @Prop() category?: string;

  /** Whether the item is completed (for today / the period). */
  @Prop({ reflect: true }) completed: boolean = false;

  /** Label of the built-in action button. Leave empty to hide the button. */
  @Prop() actionLabel: string = '';

  /** Label shown on the built-in button once `completed` is true. */
  @Prop() completedLabel: string = 'Done';

  /** Identifier sent in the `tp-action` event detail. */
  @Prop() action: string = 'complete';

  /** Shows a busy state and disables the built-in action. */
  @Prop() busy: boolean = false;

  /**
   * Emitted when the built-in action button is activated.
   * Listen in Svelte 5 with `ontp-action={(e) => …}`.
   */
  @Event({ eventName: 'tp-action', bubbles: true, composed: true })
  tpAction!: EventEmitter<ProgressCardActionDetail>;

  /** Bumped when slotted actions are added or removed later, so the footer is shown or hidden again. */
  @State() private slotVersion = 0;

  private onSlotChange = () => {
    this.slotVersion++;
  };

  private onActionClick = () => {
    if (this.completed || this.busy) return;
    this.tpAction.emit({ action: this.action });
  };

  render() {
    const value = toNumber(this.value, 0);
    const target = toNumber(this.target, 0);
    const streak = toNumber(this.streak, 0);
    const pct = percentOf(value, target);
    const hasCustomActions = !!this.el.querySelector('[slot="actions"]');
    const showFooter = !!this.actionLabel || hasCustomActions;
    const accent = isCategory(this.category) ? toneColor(this.category) : 'var(--tp-color-primary)';
    const streakText = `${streak}-${this.streakUnit} streak`;

    return (
      <Host style={{ '--tp-card-accent': accent }}>
        <article class={{ card: true, completed: this.completed }} part="card" aria-busy={this.busy ? 'true' : 'false'}>
          <header class="header">
            <span class="icon" aria-hidden="true">
              <slot name="icon">{categoryIcon(this.category)}</slot>
            </span>
            <div class="titles">
              <h3 class="heading">{this.heading}</h3>
              {this.category && <span class="category">{categoryLabel(this.category)}</span>}
            </div>
            {this.completed && (
              <span class="status">
                <span aria-hidden="true">✓</span> Completed
              </span>
            )}
          </header>

          <div class="body">
            <slot />
          </div>

          {target > 0 && (
            <div class="progress">
              <div
                class="meter"
                role="progressbar"
                aria-label={`${this.heading || 'Progress'}${this.unit ? ` (${this.unit})` : ''}`}
                aria-valuemin="0"
                aria-valuemax={String(target)}
                aria-valuenow={String(Math.min(value, target))}
                aria-valuetext={`${formatNumber(value)} of ${formatNumber(target)}${this.unit ? ` ${this.unit}` : ''}`}
              >
                <div class="fill" style={{ width: `${pct}%` }} />
              </div>
              <span class="figures">
                <strong>{formatNumber(value)}</strong> / {formatNumber(target)}
                {this.unit ? ` ${this.unit}` : ''}
              </span>
            </div>
          )}

          {streak > 0 && (
            <p class="streak">
              <span aria-hidden="true">🔥</span> {streakText}
            </p>
          )}

          {/* Always rendered (hidden when empty), so the slot exists and reports later content. */}
          <footer class={{ actions: true, hidden: !showFooter }}>
            <slot name="actions" onSlotchange={this.onSlotChange} />
            {this.actionLabel && (
              <button
                type="button"
                class="action"
                part="action"
                disabled={this.completed || this.busy}
                aria-label={this.completed ? `${this.heading}: ${this.completedLabel}` : `${this.actionLabel}: ${this.heading}`}
                onClick={this.onActionClick}
              >
                {this.completed ? `✓ ${this.completedLabel}` : this.busy ? 'Saving…' : this.actionLabel}
              </button>
            )}
          </footer>
        </article>
      </Host>
    );
  }
}
