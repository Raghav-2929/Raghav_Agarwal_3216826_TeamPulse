/**
 * Two-way binding between a reactive filter object and the page's URL search params.
 *
 *   const filters = createUrlFilters({ search: { type: 'string' }, category: { type: 'enum', values: CATEGORIES } });
 *   <input bind:value={filters.search} />            // URL updates (debounced, history.replaceState)
 *
 * - Initial state is parsed from the current URL (deep links / reloads restore filters).
 * - State → URL: canonical query string, `replaceState` navigation (no history spam).
 * - URL → state: following a link to the same route with other params updates the controls.
 */
import { untrack } from 'svelte';
import { goto } from '$app/navigation';
import { page } from '$app/state';
import { canonicalSearch, defaultFilters, filtersToSearch, parseFilters, type FilterSchema, type FilterValues } from '$lib/utils/filters';

export interface UrlFilters<S extends FilterSchema> {
  /** Reactive values — bind controls directly to these. */
  values: FilterValues<S>;
  /** Restores every field to its default. */
  reset(): void;
  /** Sets several fields at once (e.g. a filter change that also resets `page`). */
  patch(partial: Partial<FilterValues<S>>): void;
}

export function createUrlFilters<S extends FilterSchema>(schema: S, options: { debounce?: number } = {}): UrlFilters<S> {
  const debounce = options.debounce ?? 300;
  const values = $state(parseFilters(schema, page.url.searchParams)) as FilterValues<S>;
  const pathname = page.url.pathname;
  let syncedSearch = filtersToSearch(schema, values);

  // URL → state (e.g. sidebar link to the same route, back/forward)
  $effect(() => {
    // Ignore the URL of the *next* route while this page is being navigated away from.
    if (page.url.pathname !== pathname) return;
    const fromUrl = canonicalSearch(schema, page.url.searchParams);
    if (fromUrl !== syncedSearch) {
      syncedSearch = fromUrl;
      const parsed = parseFilters(schema, page.url.searchParams);
      untrack(() => Object.assign(values, parsed));
    }
  });

  // state → URL
  $effect(() => {
    const search = filtersToSearch(schema, values);
    if (search === syncedSearch) return;
    const timer = setTimeout(() => {
      if (page.url.pathname !== pathname) return;
      syncedSearch = search;
      void goto(`${pathname}${search ? `?${search}` : ''}`, { replaceState: true, keepFocus: true, noScroll: true });
    }, debounce);
    return () => clearTimeout(timer);
  });

  return {
    values,
    reset() {
      Object.assign(values, defaultFilters(schema));
    },
    patch(partial) {
      Object.assign(values, partial);
    },
  };
}
