/**
 * Unread-notification counter shown in the header. Polls `GET /notifications/unread-count`
 * every 60 s while the app shell is mounted (skipping polls while the tab is hidden).
 */
import { untrack } from 'svelte';
import { api } from '$lib/api';

export const UNREAD_POLL_INTERVAL_MS = 60_000;

class NotificationsStore {
  unread = $state(0);
  lastCheckedAt = $state<Date | null>(null);

  #timer: ReturnType<typeof setInterval> | null = null;
  #onVisible = () => {
    if (document.visibilityState === 'visible') void this.refresh();
  };

  async refresh(): Promise<void> {
    try {
      const { count } = await api.notifications.unreadCount();
      this.unread = Math.max(0, Number(count) || 0);
      this.lastCheckedAt = new Date();
    } catch {
      /* transient failures keep the previous count */
    }
  }

  /** Starts polling; returns a stop function (handy as an `$effect` cleanup). */
  start(intervalMs = UNREAD_POLL_INTERVAL_MS): () => void {
    this.stop();
    // untrack: when called from an $effect, the request must not subscribe it to session state.
    untrack(() => void this.refresh());
    this.#timer = setInterval(() => {
      if (typeof document === 'undefined' || document.visibilityState !== 'hidden') void this.refresh();
    }, intervalMs);
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', this.#onVisible);
    return () => this.stop();
  }

  stop(): void {
    if (this.#timer) clearInterval(this.#timer);
    this.#timer = null;
    if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', this.#onVisible);
  }

  markedRead(n = 1): void {
    this.unread = Math.max(0, this.unread - n);
  }

  reset(): void {
    this.unread = 0;
  }
}

export const notifications = new NotificationsStore();
