import { describe, expect, it } from 'vitest';
import { activeFilterCount, canonicalSearch, defaultFilters, filtersToSearch, parseFilters, serializeFilters, toApiQuery, type FilterSchema } from './filters';

const schema = {
  search: { type: 'string', maxLength: 10 },
  status: { type: 'enum', values: ['upcoming', 'active', 'completed'] },
  joined: { type: 'boolean' },
  from: { type: 'date' },
  page: { type: 'number', default: 1, min: 1, max: 50 },
} satisfies FilterSchema;

describe('URL filter (de)serialisation', () => {
  it('provides defaults', () => {
    expect(defaultFilters(schema)).toEqual({ search: '', status: '', joined: false, from: '', page: 1 });
  });

  it('parses valid params and rejects invalid ones', () => {
    const params = new URLSearchParams('search=yoga&status=active&joined=true&from=2026-11-01&page=3&unknown=x');
    expect(parseFilters(schema, params)).toEqual({ search: 'yoga', status: 'active', joined: true, from: '2026-11-01', page: 3 });

    const bad = new URLSearchParams('status=archived&joined=maybe&from=yesterday&page=-4');
    expect(parseFilters(schema, bad)).toEqual({ search: '', status: '', joined: false, from: '', page: 1 });
  });

  it('clamps numbers and truncates long strings', () => {
    const params = new URLSearchParams('page=999&search=abcdefghijklmnop');
    const parsed = parseFilters(schema, params);
    expect(parsed.page).toBe(50);
    expect(parsed.search).toBe('abcdefghij');
  });

  it('serialises only non-default values in schema order', () => {
    const qs = serializeFilters(schema, { page: 2, search: 'run', status: '', joined: true, from: '' }).toString();
    expect(qs).toBe('search=run&joined=true&page=2');
    expect(filtersToSearch(schema, defaultFilters(schema))).toBe('');
    expect(filtersToSearch(schema, { search: '   ' })).toBe('');
  });

  it('round-trips and canonicalises', () => {
    const values = { search: 'hike', status: 'completed', joined: false, from: '2026-10-01', page: 1 };
    const qs = filtersToSearch(schema, values);
    expect(parseFilters(schema, new URLSearchParams(qs))).toEqual(values);
    expect(canonicalSearch(schema, new URLSearchParams('page=1&status=bogus&search=hike'))).toBe('search=hike');
  });

  it('counts active filters, optionally ignoring keys', () => {
    expect(activeFilterCount(schema, { search: 'x', status: 'active', joined: false, from: '', page: 4 })).toBe(3);
    expect(activeFilterCount(schema, { search: 'x', status: 'active', joined: false, from: '', page: 4 }, ['page'])).toBe(2);
    expect(activeFilterCount(schema, defaultFilters(schema))).toBe(0);
  });

  it('maps values to API query params', () => {
    expect(toApiQuery({ search: '  run ', category: '', joined: true, page: 2 }, { joined: 'joined_only' })).toEqual({
      search: 'run',
      category: undefined,
      joined_only: true,
      page: 2,
    });
  });
});
