import { Component, Host, Prop, h } from '@stencil/core';
import { deltaTrend, formatDelta } from '../../utils/format';

/**
 * Key-figure tile (KPI) with optional delta and hint.
 *
 * @slot - Extra content rendered after the value.
 * @slot icon - Icon rendered next to the label.
 * @part tile - The tile container.
 * @part value - The value element.
 */
@Component({
  tag: 'tp-stat-tile',
  styleUrl: 'tp-stat-tile.css',
  shadow: true,
})
export class TpStatTile {
  /** What the figure measures. */
  @Prop() label: string = '';

  /** The figure itself (number or pre-formatted string). */
  @Prop() value: string | number = '';

  /** Change vs. a previous period: a number (`3`, `-2`) or display string (`+12%`). */
  @Prop() delta?: string | number;

  /** Inverts colouring when a decrease is good (e.g. "suppressed days"). */
  @Prop() invertDelta: boolean = false;

  /** Secondary explanatory text. */
  @Prop() hint: string = '';

  render() {
    const trend = deltaTrend(this.delta);
    const good = trend === 'flat' || trend === null ? null : (trend === 'up') !== this.invertDelta;
    const deltaText = formatDelta(this.delta);
    return (
      <Host>
        <div class="tile" part="tile">
          <div class="label">
            <slot name="icon" />
            <span>{this.label}</span>
          </div>
          <div class="value" part="value">
            {this.value === '' || this.value === null || this.value === undefined ? '–' : this.value}
            <slot />
          </div>
          {trend && (
            <div class={{ delta: true, good: good === true, bad: good === false }}>
              <span aria-hidden="true">{trend === 'up' ? '▲' : trend === 'down' ? '▼' : '■'}</span>
              <span class="sr-only">{trend === 'up' ? 'Increased by' : trend === 'down' ? 'Decreased by' : 'Unchanged'}</span> {deltaText}
            </div>
          )}
          {this.hint && <div class="hint">{this.hint}</div>}
        </div>
      </Host>
    );
  }
}
