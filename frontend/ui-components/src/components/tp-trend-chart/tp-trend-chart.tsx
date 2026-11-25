import { Component, Element, Event, EventEmitter, Host, Prop, State, h } from '@stencil/core';
import type { TrendChartType, TrendPointSelectDetail, TrendSeries } from '../../types';
import { parseArrayProp, toNumber } from '../../utils/parse';
import { formatLongDate, formatNumber, formatShortDate, isIsoDate } from '../../utils/format';
import { alignSeries, allIntegers, collectXValues, labelStride, lineSegments, maxValue, niceScale, paletteColor, round } from '../../utils/chart';

let chartIds = 0;

interface PreparedSeries {
  label: string;
  color: string;
  values: (number | null)[];
}

/**
 * Dependency-free SVG line / bar chart for daily trends.
 *
 * - `null` y values are rendered as gaps (lines break, bars are replaced by a hatched marker) —
 *   used for k-anonymity–suppressed days on team insights.
 * - Hover or focus a column to see a tooltip; ←/→/Home/End move between columns,
 *   Enter/Space (or click) emits `tp-point-select`.
 * - A visually hidden data table mirrors the chart for screen readers.
 *
 * @part svg - The chart `<svg>`.
 * @part tooltip - The tooltip container.
 * @part legend - The legend list.
 */
@Component({
  tag: 'tp-trend-chart',
  styleUrl: 'tp-trend-chart.css',
  shadow: true,
})
export class TpTrendChart {
  @Element() el!: HTMLElement;

  /**
   * Series to plot. Array (JS property) or JSON string (attribute) of
   * `{label, points: [{x: 'YYYY-MM-DD', y: number | null}], color?}`.
   */
  @Prop() series: TrendSeries[] | string = [];

  /** `line` or `bar`. */
  @Prop() type: TrendChartType = 'line';

  /** Chart height in CSS pixels. */
  @Prop() height: number = 240;

  /** Optional y-axis title. */
  @Prop() yLabel: string = '';

  /** Accessible name of the chart. */
  @Prop() label: string = 'Trend chart';

  /** Message rendered when there is nothing to plot. */
  @Prop() emptyText: string = 'No data for this period.';

  /** Text used for `null` points in tooltips and the data table. */
  @Prop() gapLabel: string = 'No data';

  /** Shows the legend (always hidden for a single unlabeled series). */
  @Prop() showLegend: boolean = true;

  @State() width: number = 640;
  @State() activeIndex: number | null = null;

  /**
   * Emitted when a column is activated by click, Enter or Space.
   * Listen in Svelte 5 with `ontp-point-select={(e) => …}`.
   */
  @Event({ eventName: 'tp-point-select', bubbles: true, composed: true })
  pointSelect!: EventEmitter<TrendPointSelectDetail>;

  private resizeObserver?: ResizeObserver;
  private readonly uid = `tp-chart-${++chartIds}`;
  private focusIndex = 0;

  connectedCallback() {
    if (typeof ResizeObserver !== 'undefined' && !this.resizeObserver) {
      this.resizeObserver = new ResizeObserver((entries) => {
        const w = Math.floor(entries[0]?.contentRect.width ?? 0);
        if (w > 0 && Math.abs(w - this.width) > 1) this.width = w;
      });
      this.resizeObserver.observe(this.el);
    }
  }

  disconnectedCallback() {
    this.resizeObserver?.disconnect();
    this.resizeObserver = undefined;
  }

  private prepare(): { xs: string[]; series: PreparedSeries[] } {
    const raw = parseArrayProp<TrendSeries>(this.series).filter((s) => s && Array.isArray(s.points));
    const xs = collectXValues(raw);
    const series = raw.map((s, i) => ({
      label: s.label ?? `Series ${i + 1}`,
      color: s.color || paletteColor(i),
      values: alignSeries(s, xs),
    }));
    return { xs, series };
  }

  private emitSelect(index: number, xs: string[], series: PreparedSeries[]) {
    this.pointSelect.emit({
      index,
      x: xs[index],
      values: series.map((s) => ({ label: s.label, y: s.values[index] })),
    });
  }

  private onKeyDown(event: KeyboardEvent, index: number, xs: string[], series: PreparedSeries[]) {
    let next: number | null = null;
    switch (event.key) {
      case 'ArrowRight':
      case 'ArrowDown':
        next = Math.min(xs.length - 1, index + 1);
        break;
      case 'ArrowLeft':
      case 'ArrowUp':
        next = Math.max(0, index - 1);
        break;
      case 'Home':
        next = 0;
        break;
      case 'End':
        next = xs.length - 1;
        break;
      case 'Enter':
      case ' ':
        event.preventDefault();
        this.emitSelect(index, xs, series);
        return;
      default:
        return;
    }
    event.preventDefault();
    this.focusIndex = next;
    this.activeIndex = next;
    const target = this.el.shadowRoot?.querySelector<SVGElement>(`[data-hit="${next}"]`);
    target?.focus();
  }

  private describe(index: number, xs: string[], series: PreparedSeries[]): string {
    const x = isIsoDate(xs[index]) ? formatLongDate(xs[index]) : xs[index];
    const parts = series.map((s) => `${s.label}: ${s.values[index] === null ? this.gapLabel : formatNumber(s.values[index])}`);
    return `${x}. ${parts.join(', ')}`;
  }

  private renderTooltip(index: number, xs: string[], series: PreparedSeries[], xAt: (i: number) => number, top: number) {
    const x = xAt(index);
    const align = x < 90 ? 'start' : x > this.width - 90 ? 'end' : 'center';
    const allNull = series.every((s) => s.values[index] === null);
    return (
      <div class={{ tooltip: true, [`align-${align}`]: true }} part="tooltip" style={{ left: `${x}px`, top: `${top}px` }} aria-hidden="true">
        <div class="tooltip-title">{isIsoDate(xs[index]) ? formatLongDate(xs[index]) : xs[index]}</div>
        {allNull ? (
          <div class="tooltip-gap">{this.gapLabel}</div>
        ) : (
          series.map((s) => (
            <div class="tooltip-row">
              <span class="swatch" style={{ background: s.color }} />
              <span class="tooltip-label">{s.label}</span>
              <span class="tooltip-value">{s.values[index] === null ? this.gapLabel : formatNumber(s.values[index])}</span>
            </div>
          ))
        )}
      </div>
    );
  }

  render() {
    const { xs, series } = this.prepare();
    const height = Math.max(120, toNumber(this.height, 240));

    if (xs.length === 0 || series.length === 0) {
      return (
        <Host>
          <div class="empty" style={{ minHeight: `${Math.min(height, 160)}px` }} role="note">
            {this.emptyText}
          </div>
        </Host>
      );
    }

    const width = Math.max(240, this.width);
    const pad = { top: 16, right: 16, bottom: 30, left: this.yLabel ? 56 : 40 };
    const plotW = width - pad.left - pad.right;
    const plotH = height - pad.top - pad.bottom;
    const aligned = series.map((s) => s.values);
    const scale = niceScale(maxValue(aligned), { targetTicks: 4, integer: allIntegers(aligned) });
    const yMax = scale.max;
    const ticks = scale.ticks;
    const isBar = this.type === 'bar';
    const n = xs.length;
    const band = plotW / n;
    const xAt = (i: number) => (isBar ? pad.left + band * (i + 0.5) : n === 1 ? pad.left + plotW / 2 : pad.left + (i / (n - 1)) * plotW);
    const yAt = (v: number) => pad.top + plotH - (v / yMax) * plotH;
    const stride = labelStride(n, Math.max(2, Math.floor(plotW / 64)));
    const showDots = n <= 45;
    const gapColumns = xs.map((_, i) => series.every((s) => s.values[i] === null));
    const hitWidth = n === 1 ? plotW : isBar ? band : plotW / (n - 1);
    const groupW = band * 0.72;
    const barW = groupW / series.length;
    const gapW = isBar ? groupW : Math.max(6, Math.min(hitWidth * 0.7, 28));
    const active = this.activeIndex;
    const tabIndex = Math.min(this.focusIndex, n - 1);
    const showLegend = this.showLegend && (series.length > 1 || !!series[0].label);
    const hatchId = `${this.uid}-hatch`;

    return (
      <Host>
        <figure class="chart">
          <div class="plot" style={{ height: `${height}px` }} onMouseLeave={() => (this.activeIndex = null)}>
            <svg
              part="svg"
              width={width}
              height={height}
              viewBox={`0 0 ${width} ${height}`}
              role="group"
              aria-label={this.label}
            >
              <defs>
                <pattern id={hatchId} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                  <line x1="0" y1="0" x2="0" y2="6" class="hatch-line" stroke-width="2" />
                </pattern>
              </defs>

              {/* grid + y axis */}
              <g class="grid" aria-hidden="true">
                {ticks.map((t) => (
                  <g>
                    <line x1={pad.left} x2={width - pad.right} y1={round(yAt(t))} y2={round(yAt(t))} />
                    <text x={pad.left - 8} y={round(yAt(t))} class="y-tick" text-anchor="end" dominant-baseline="middle">
                      {formatNumber(t)}
                    </text>
                  </g>
                ))}
                {this.yLabel && (
                  <text class="axis-label" x={-(pad.top + plotH / 2)} y={14} transform="rotate(-90)" text-anchor="middle">
                    {this.yLabel}
                  </text>
                )}
              </g>

              {/* suppressed / missing columns */}
              <g class="gaps" aria-hidden="true">
                {gapColumns.map((isGap, i) =>
                  isGap ? (
                    <rect class="gap" x={round(xAt(i) - gapW / 2)} y={pad.top} width={round(gapW)} height={plotH} fill={`url(#${hatchId})`} />
                  ) : null,
                )}
              </g>

              {/* data */}
              <g class="data" aria-hidden="true">
                {isBar
                  ? series.map((s, si) =>
                      s.values.map((v, i) =>
                        v === null ? null : (
                          <rect
                            class={{ bar: true, dim: active !== null && active !== i }}
                            x={round(xAt(i) - groupW / 2 + si * barW + 0.5)}
                            y={round(yAt(v))}
                            width={round(Math.max(1, barW - 1))}
                            height={round(Math.max(0, pad.top + plotH - yAt(v)))}
                            rx="2"
                            fill={s.color}
                          />
                        ),
                      ),
                    )
                  : series.map((s) => {
                      const segments = lineSegments(s.values, xAt, yAt);
                      return (
                        <g class="series">
                          {segments.map((seg) => (seg.points > 1 ? <path class="line" d={seg.d} stroke={s.color} fill="none" /> : null))}
                          {s.values.map((v, i) => {
                            if (v === null) return null;
                            const isolated = (i === 0 || s.values[i - 1] === null) && (i === n - 1 || s.values[i + 1] === null);
                            if (!showDots && !isolated && active !== i) return null;
                            return <circle class={{ dot: true, active: active === i }} cx={round(xAt(i))} cy={round(yAt(v))} r={active === i ? 5 : 3.5} fill={s.color} />;
                          })}
                        </g>
                      );
                    })}
              </g>

              {/* active guide */}
              {active !== null && active < n && (
                <line class="guide" aria-hidden="true" x1={round(xAt(active))} x2={round(xAt(active))} y1={pad.top} y2={pad.top + plotH} />
              )}

              {/* x axis labels */}
              <g class="x-axis" aria-hidden="true">
                {xs.map((x, i) =>
                  i % stride === 0 ? (
                    <text x={round(xAt(i))} y={height - 8} text-anchor="middle" class="x-tick">
                      {formatShortDate(x)}
                    </text>
                  ) : null,
                )}
              </g>

              {/* interaction layer: one roving tab stop */}
              <g class="hits">
                {xs.map((_, i) => (
                  <rect
                    class="hit"
                    data-hit={i}
                    x={round(xAt(i) - hitWidth / 2)}
                    y={pad.top}
                    width={round(hitWidth)}
                    height={plotH}
                    tabindex={i === tabIndex ? 0 : -1}
                    role="button"
                    aria-label={this.describe(i, xs, series)}
                    onMouseEnter={() => (this.activeIndex = i)}
                    onFocus={() => {
                      this.focusIndex = i;
                      this.activeIndex = i;
                    }}
                    onBlur={() => (this.activeIndex = null)}
                    onClick={() => this.emitSelect(i, xs, series)}
                    onKeyDown={(ev: KeyboardEvent) => this.onKeyDown(ev, i, xs, series)}
                  />
                ))}
              </g>
            </svg>
            {active !== null && active < n && this.renderTooltip(active, xs, series, xAt, pad.top)}
          </div>

          {showLegend && (
            <ul class="legend" part="legend" aria-label="Legend">
              {series.map((s) => (
                <li>
                  <span class="swatch" style={{ background: s.color }} />
                  {s.label}
                </li>
              ))}
              {gapColumns.some(Boolean) && (
                <li class="legend-gap">
                  <span class="swatch hatch" />
                  {this.gapLabel}
                </li>
              )}
            </ul>
          )}

          <table class="sr-only">
            <caption>{this.label}</caption>
            <thead>
              <tr>
                <th scope="col">{isIsoDate(xs[0]) ? 'Date' : 'Label'}</th>
                {series.map((s) => (
                  <th scope="col">{s.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {xs.map((x, i) => (
                <tr>
                  <th scope="row">{isIsoDate(x) ? formatLongDate(x) : x}</th>
                  {series.map((s) => (
                    <td>{s.values[i] === null ? this.gapLabel : formatNumber(s.values[i])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </figure>
      </Host>
    );
  }
}
