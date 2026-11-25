import { Component, Host, Prop, h } from '@stencil/core';
import { formatLongDate } from '../../utils/format';

/**
 * Achievement badge — earned (with award date) or locked.
 *
 * @part badge - The badge container.
 * @part medal - The circular icon.
 */
@Component({
  tag: 'tp-badge',
  styleUrl: 'tp-badge.css',
  shadow: true,
})
export class TpBadge {
  /** Emoji or short text rendered inside the medal. */
  @Prop() icon: string = '🏅';

  /** Badge name. */
  @Prop() name: string = '';

  /** What the badge is awarded for. */
  @Prop() description: string = '';

  /** Award timestamp (ISO date or datetime). */
  @Prop() awardedAt: string = '';

  /** Renders the badge greyed out with a lock. */
  @Prop({ reflect: true }) locked: boolean = false;

  /** Compact layout (icon + name only). */
  @Prop({ reflect: true }) compact: boolean = false;

  render() {
    const status = this.locked ? 'Locked' : this.awardedAt ? `Earned ${formatLongDate(this.awardedAt)}` : 'Earned';
    const accessibleName = `${this.name} badge. ${status}.${this.description ? ` ${this.description}` : ''}`;
    return (
      <Host>
        <figure class={{ badge: true, locked: this.locked, compact: this.compact }} part="badge" role="group" aria-label={accessibleName}>
          <div class="medal" part="medal" aria-hidden="true">
            <span class="icon">{this.icon}</span>
            {this.locked && <span class="lock">🔒</span>}
          </div>
          <figcaption aria-hidden="true">
            <span class="name">{this.name}</span>
            {!this.compact && this.description && <span class="description">{this.description}</span>}
            {!this.compact && <span class="meta">{status}</span>}
          </figcaption>
        </figure>
      </Host>
    );
  }
}
