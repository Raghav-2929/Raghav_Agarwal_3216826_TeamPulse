/** Transient toast messages (rendered by `Toasts.svelte` in an ARIA live region). */
import { errorMessage } from '$lib/api/errors';

export type ToastKind = 'success' | 'error' | 'info';

export interface Toast {
  id: number;
  kind: ToastKind;
  message: string;
}

class ToastStore {
  items = $state<Toast[]>([]);
  #nextId = 1;
  #timers = new Map<number, ReturnType<typeof setTimeout>>();

  push(kind: ToastKind, message: string, timeoutMs = kind === 'error' ? 7000 : 4000): number {
    const id = this.#nextId++;
    this.items = [...this.items.slice(-4), { id, kind, message }];
    if (timeoutMs > 0) this.#timers.set(id, setTimeout(() => this.dismiss(id), timeoutMs));
    return id;
  }

  success(message: string): number {
    return this.push('success', message);
  }

  info(message: string): number {
    return this.push('info', message);
  }

  /** Shows an error toast; accepts an `ApiError` (shows its `detail`) or any thrown value. */
  error(error: unknown, fallback?: string): number {
    return this.push('error', typeof error === 'string' ? error : errorMessage(error, fallback));
  }

  dismiss(id: number): void {
    const timer = this.#timers.get(id);
    if (timer) clearTimeout(timer);
    this.#timers.delete(id);
    this.items = this.items.filter((t) => t.id !== id);
  }

  clear(): void {
    for (const timer of this.#timers.values()) clearTimeout(timer);
    this.#timers.clear();
    this.items = [];
  }
}

export const toasts = new ToastStore();
