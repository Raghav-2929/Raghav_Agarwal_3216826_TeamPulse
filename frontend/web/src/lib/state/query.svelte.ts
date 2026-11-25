/**
 * Tiny rune-based async resource for component-scoped data loading.
 *
 *   const habits = createQuery({
 *     key: () => ({ ...filters }),                       // reactive inputs (tracked)
 *     fetch: (key, signal) => api.habits.list(key, { signal }),
 *     debounce: 250,                                     // debounce re-fetches (not the first load)
 *   });
 *   habits.data / habits.error / habits.loading / habits.refetch()
 *
 * Re-runs whenever anything read inside `key()` changes; the in-flight request is aborted.
 * Must be called during component initialisation (it registers an `$effect`).
 */
import { untrack } from 'svelte';
import { ApiError, isApiError } from '$lib/api/errors';

export interface Query<T> {
  readonly data: T | undefined;
  readonly error: ApiError | null;
  /** True while a request is in flight. */
  readonly loading: boolean;
  /** True until the first response (success or error) arrives (stays true while disabled). */
  readonly initialLoading: boolean;
  refetch(): void;
  /** Locally replaces the data (optimistic updates). */
  set(data: T | undefined): void;
}

export interface QueryOptions<K, T> {
  key: () => K;
  fetch: (key: K, signal: AbortSignal) => Promise<T>;
  debounce?: number;
  enabled?: (key: K) => boolean;
}

function toApiError(error: unknown): ApiError {
  if (isApiError(error)) return error;
  return new ApiError({ status: 0, detail: error instanceof Error ? error.message : undefined });
}

function isAbort(error: unknown): boolean {
  return error instanceof Error && error.name === 'AbortError';
}

export function createQuery<K, T>(options: QueryOptions<K, T>): Query<T> {
  let data = $state<T | undefined>(undefined);
  let error = $state<ApiError | null>(null);
  let loading = $state(true);
  let initialLoading = $state(true);
  let version = $state(0);
  let hasRun = false;

  $effect(() => {
    void version;
    const key = options.key();
    const enabled = untrack(() => (options.enabled ? options.enabled(key) : true));
    if (!enabled) {
      // Disabled queries are idle; `initialLoading` stays true until a first real fetch settles.
      untrack(() => (loading = false));
      return;
    }

    const controller = new AbortController();
    const execute = () =>
      untrack(() => {
        loading = true;
        options
          .fetch(key, controller.signal)
          .then((result) => {
            if (controller.signal.aborted) return;
            data = result;
            error = null;
          })
          .catch((e: unknown) => {
            if (controller.signal.aborted || isAbort(e)) return;
            error = toApiError(e);
          })
          .finally(() => {
            if (controller.signal.aborted) return;
            loading = false;
            initialLoading = false;
          });
      });

    let timer: ReturnType<typeof setTimeout> | undefined;
    if (options.debounce && hasRun) {
      untrack(() => (loading = true));
      timer = setTimeout(execute, options.debounce);
    } else {
      execute();
    }
    hasRun = true;

    return () => {
      if (timer) clearTimeout(timer);
      controller.abort();
    };
  });

  return {
    get data() {
      return data;
    },
    get error() {
      return error;
    },
    get loading() {
      return loading;
    },
    get initialLoading() {
      return initialLoading;
    },
    refetch() {
      version++;
    },
    set(next) {
      data = next;
    },
  };
}
