/**
 * Schema-driven (de)serialisation of list filters to/from URL search params, so filter state is
 * shareable, bookmarkable and survives reloads. Pure functions — the rune wrapper lives in
 * `$lib/state/url-filters.svelte.ts`.
 */

export type FilterField =
  | { type: 'string'; default?: string; maxLength?: number }
  | { type: 'enum'; values: readonly string[]; default?: string }
  | { type: 'boolean'; default?: boolean }
  | { type: 'number'; default?: number; min?: number; max?: number }
  | { type: 'date'; default?: string };

export type FilterSchema = Record<string, FilterField>;

export type FilterValue<F extends FilterField> = F extends { type: 'boolean' } ? boolean : F extends { type: 'number' } ? number : string;

export type FilterValues<S extends FilterSchema> = { [K in keyof S]: FilterValue<S[K]> };

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const TRUE_VALUES = new Set(['1', 'true', 'yes', 'on']);
const FALSE_VALUES = new Set(['0', 'false', 'no', 'off']);

function fieldDefault(field: FilterField): string | number | boolean {
  switch (field.type) {
    case 'boolean':
      return field.default ?? false;
    case 'number':
      return field.default ?? 0;
    default:
      return field.default ?? '';
  }
}

/** Default values for every field. */
export function defaultFilters<S extends FilterSchema>(schema: S): FilterValues<S> {
  const out: Record<string, unknown> = {};
  for (const [key, field] of Object.entries(schema)) out[key] = fieldDefault(field);
  return out as FilterValues<S>;
}

/** Parses one raw value; invalid input falls back to the field default. */
export function parseField(field: FilterField, raw: string | null): string | number | boolean {
  if (raw === null) return fieldDefault(field);
  const value = raw.trim();
  switch (field.type) {
    case 'string':
      return field.maxLength ? raw.slice(0, field.maxLength) : raw;
    case 'enum':
      return field.values.includes(value) ? value : fieldDefault(field);
    case 'boolean':
      if (TRUE_VALUES.has(value.toLowerCase())) return true;
      if (FALSE_VALUES.has(value.toLowerCase())) return false;
      return fieldDefault(field);
    case 'number': {
      const n = Number(value);
      if (value === '' || !Number.isFinite(n)) return fieldDefault(field);
      const int = Math.trunc(n);
      if (field.min !== undefined && int < field.min) return fieldDefault(field);
      if (field.max !== undefined && int > field.max) return field.max;
      return int;
    }
    case 'date':
      return ISO_DATE.test(value) ? value : fieldDefault(field);
  }
}

/** Reads filter values from URL search params (unknown params are ignored). */
export function parseFilters<S extends FilterSchema>(schema: S, params: URLSearchParams): FilterValues<S> {
  const out: Record<string, unknown> = {};
  for (const [key, field] of Object.entries(schema)) out[key] = parseField(field, params.get(key));
  return out as FilterValues<S>;
}

/**
 * Serialises values to search params in schema order, omitting defaults and empty strings so
 * URLs stay short and canonical.
 */
export function serializeFilters<S extends FilterSchema>(schema: S, values: Partial<FilterValues<S>>): URLSearchParams {
  const params = new URLSearchParams();
  for (const [key, field] of Object.entries(schema)) {
    const value = (values as Record<string, unknown>)[key];
    if (value === undefined || value === null) continue;
    if (value === fieldDefault(field)) continue;
    if (field.type === 'boolean') {
      params.set(key, value ? 'true' : 'false');
    } else if (field.type === 'string') {
      const text = String(value);
      if (text.trim() !== '') params.set(key, text);
    } else if (String(value) !== '') {
      params.set(key, String(value));
    }
  }
  return params;
}

/** Canonical query string (without `?`) for a set of values. */
export function filtersToSearch<S extends FilterSchema>(schema: S, values: Partial<FilterValues<S>>): string {
  return serializeFilters(schema, values).toString();
}

/** Canonical form of arbitrary search params under a schema (drops unknown/invalid values). */
export function canonicalSearch<S extends FilterSchema>(schema: S, params: URLSearchParams): string {
  return filtersToSearch(schema, parseFilters(schema, params));
}

/** Number of fields that differ from their defaults (for "n filters active" badges). */
export function activeFilterCount<S extends FilterSchema>(schema: S, values: Partial<FilterValues<S>>, ignore: (keyof S)[] = []): number {
  let n = 0;
  for (const [key, field] of Object.entries(schema)) {
    if (ignore.includes(key)) continue;
    const value = (values as Record<string, unknown>)[key];
    if (value !== undefined && value !== fieldDefault(field) && !(typeof value === 'string' && value.trim() === '')) n++;
  }
  return n;
}

/**
 * Converts filter values to API query params: empty strings become `undefined` (dropped by the
 * HTTP client), strings are trimmed, and `rename` maps UI keys to API keys.
 */
export function toApiQuery<T extends Record<string, unknown>>(values: T, rename: Partial<Record<keyof T, string>> = {}): Record<string, string | number | boolean | undefined> {
  const out: Record<string, string | number | boolean | undefined> = {};
  for (const [key, value] of Object.entries(values)) {
    const target = (rename as Record<string, string | undefined>)[key] ?? key;
    if (typeof value === 'string') {
      const trimmed = value.trim();
      out[target] = trimmed === '' ? undefined : trimmed;
    } else if (typeof value === 'number' || typeof value === 'boolean') {
      out[target] = value;
    }
  }
  return out;
}
