import { Component, Host, Prop, h } from '@stencil/core';
import type { Tone } from '../../types';
import { clamp, percentOf, toNumber } from '../../utils/parse';
import { formatNumber, toneColor } from '../../utils/format';

/**
 * Circular progress indicator (ARIA `progressbar`).
 *
 * @slot - Centre content. Defaults to the rounded percentage.
 * @part ring - The element carrying the `progressbar` role.
 * @part center - Wrapper of the centre content.
 */
@Component({
  tag: 'tp-progress-ring',
  styleUrl: 'tp-progress-ring.css',
  shadow: true,
})
export class TpProgressRing {
  /** Current value. */
  @Prop() value: number = 0;

  /** Value that represents 100 %. */
  @Prop() max: number = 100;

  /** Outer diameter in CSS pixels. */
  @Prop() size: number = 120;

  /** Thickness of the ring in CSS pixels. */
  @Prop() strokeWidth: number = 10;

  /** Accessible name announced by assistive technology. */
  @Prop() label: string = 'Progress';

  /** Colour tone: `primary | success | warning | danger | neutral` or a category (`fitness`, `sleep`, …). */
  @Prop() tone: Tone = 'primary';

  render() {
    const max = Math.max(0, toNumber(this.max, 100));
    const value = toNumber(this.value, 0);
    const size = Math.max(24, toNumber(this.size, 120));
    const stroke = clamp(toNumber(this.strokeWidth, 10), 1, size / 2 - 1);
    const radius = (size - stroke) / 2;
    const circumference = 2 * Math.PI * radius;
    const pct = percentOf(value, max);
    const rounded = Math.round(pct);
    const offset = circumference * (1 - pct / 100);
    const centre = size / 2;

    return (
      <Host style={{ '--tp-ring-size': `${size}px` }}>
        <div
          class="ring"
          part="ring"
          role="progressbar"
          aria-label={this.label}
          aria-valuemin="0"
          aria-valuemax={String(max)}
          aria-valuenow={String(clamp(value, 0, max))}
          aria-valuetext={`${formatNumber(value)} of ${formatNumber(max)} (${rounded}%)`}
        >
          <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true" focusable="false">
            <circle class="track" cx={centre} cy={centre} r={radius} fill="none" stroke-width={stroke} />
            <circle
              class="indicator"
              cx={centre}
              cy={centre}
              r={radius}
              fill="none"
              stroke={toneColor(this.tone)}
              stroke-width={stroke}
              stroke-linecap={pct > 0 ? 'round' : 'butt'}
              stroke-dasharray={`${circumference} ${circumference}`}
              stroke-dashoffset={offset}
              transform={`rotate(-90 ${centre} ${centre})`}
            />
          </svg>
          <div class="center" part="center">
            <slot>
              <span class="pct">{rounded}%</span>
            </slot>
          </div>
        </div>
      </Host>
    );
  }
}
