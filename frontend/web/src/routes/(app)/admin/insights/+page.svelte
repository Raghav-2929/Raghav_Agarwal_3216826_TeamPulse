<script lang="ts">
  import type { TrendSeries } from '@teampulse/ui-components';
  import { api } from '$lib/api';
  import DateRangePicker from '$lib/components/DateRangePicker.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { createUrlFilters } from '$lib/state/url-filters.svelte';
  import { formatRange, presetRange, todayISO, validateRange } from '$lib/utils/dates';
  import type { FilterSchema } from '$lib/utils/filters';

  const today = todayISO();
  const defaults = presetRange('30d', today);
  const schema = {
    from: { type: 'date', default: defaults.from },
    to: { type: 'date', default: defaults.to },
  } satisfies FilterSchema;

  const filters = createUrlFilters(schema);
  const f = filters.values;
  const rangeError = $derived(validateRange({ from: f.from, to: f.to }, { today }));

  const teams = createQuery({ key: () => 'teams', fetch: (_k, signal) => api.teams.list({ signal }) });
  const org = createQuery({
    key: () => ({ from: f.from, to: f.to, valid: !rangeError }),
    enabled: (k) => k.valid,
    fetch: (k, signal) => api.insights.org({ from: k.from, to: k.to }, { signal }),
    debounce: 200,
  });

  const teamName = $derived(new Map((teams.data ?? []).map((t) => [t.id, t.name])));
  const rows = $derived(
    [...(org.data?.teams ?? [])]
      .map((t) => ({ ...t, name: teamName.get(t.team_id) ?? `Team ${t.team_id.slice(0, 8)}` }))
      .sort((a, b) => b.completions - a.completions),
  );
  // Categorical x axis (team names) on the shared trend-chart component.
  const series = $derived<TrendSeries[]>([
    { label: 'Completions', color: 'var(--tp-chart-1)', points: rows.map((r) => ({ x: r.name, y: r.completions })) },
  ]);
  const totals = $derived({
    completions: rows.reduce((s, r) => s + r.completions, 0),
    suppressed: rows.reduce((s, r) => s + r.suppressed_days, 0),
  });
</script>

<svelte:head>
  <title>Org insights · Admin · TeamPulse</title>
</svelte:head>

<PageHeader title="Organisation insights" description="Per-team aggregates across the organisation." />

<div class="notice notice-info" role="note">
  <span class="notice-icon" aria-hidden="true">🛡️</span>
  <p class="small">
    Figures are aggregated per team and k-anonymised: days with fewer than {org.data?.min_cohort_size ?? 3} active members in a team are excluded
    from that team's totals. No individual-level wellness data is available here.
  </p>
</div>

<form class="filters" aria-label="Org insight filters" onsubmit={(e) => e.preventDefault()}>
  <DateRangePicker bind:from={f.from} bind:to={f.to} idPrefix="org-range" />
</form>

{#if rangeError}
  <EmptyState icon="📅" title="Adjust the date range" message={rangeError} />
{:else if org.initialLoading}
  <Loading label="Loading organisation insights…" />
{:else if org.error}
  <ErrorState error={org.error} retry={org.refetch} />
{:else if rows.length === 0}
  <EmptyState icon="🌐" title="No team data for this period" />
{:else}
  <section class="grid-tiles" aria-label="Organisation totals">
    <tp-stat-tile label="Teams" value={String(rows.length)}></tp-stat-tile>
    <tp-stat-tile label="Completions" value={String(totals.completions)} hint={org.data ? formatRange(org.data) : ''}></tp-stat-tile>
    <tp-stat-tile label="Suppressed team-days" value={String(totals.suppressed)} hint="below the cohort threshold"></tp-stat-tile>
  </section>

  <section class="card" aria-labelledby="org-chart-title">
    <h2 id="org-chart-title" class="section-title">Completions by team</h2>
    <tp-trend-chart {series} type="bar" height={260} label="Completions by team" yLabel="Completions" showLegend={false}></tp-trend-chart>
  </section>

  <div class="table-wrap">
    <table class="table">
      <caption class="sr-only">Per-team aggregates</caption>
      <thead>
        <tr>
          <th scope="col">Team</th>
          <th scope="col">Completions</th>
          <th scope="col">Active days</th>
          <th scope="col">Suppressed days</th>
          <th scope="col">Avg active members</th>
        </tr>
      </thead>
      <tbody>
        {#each rows as row (row.team_id)}
          <tr>
            <td><strong>{row.name}</strong></td>
            <td class="num">{row.completions}</td>
            <td class="num">{row.active_days}</td>
            <td class="num">{row.suppressed_days}</td>
            <td class="num">{row.avg_active_members.toFixed(1)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .section-title {
    margin-bottom: var(--tp-space-4);
    font-size: var(--tp-font-size-lg);
  }
</style>
