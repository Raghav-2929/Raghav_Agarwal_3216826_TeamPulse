<script lang="ts">
  import type { TrendPointSelectDetail } from '@teampulse/ui-components';
  import { api } from '$lib/api';
  import { CATEGORIES, type Category } from '$lib/api/types';
  import DateRangePicker from '$lib/components/DateRangePicker.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { createUrlFilters } from '$lib/state/url-filters.svelte';
  import { CATEGORY_META, CATEGORY_OPTIONS, categoryLabel } from '$lib/utils/categories';
  import { formatDate, formatRange, presetRange, todayISO, validateRange } from '$lib/utils/dates';
  import type { FilterSchema } from '$lib/utils/filters';
  import { categoryShares, percent, personalDailySeries } from '$lib/utils/insights';

  const today = todayISO();
  const defaults = presetRange('30d', today);
  const schema = {
    from: { type: 'date', default: defaults.from },
    to: { type: 'date', default: defaults.to },
    category: { type: 'enum', values: CATEGORIES },
  } satisfies FilterSchema;

  const filters = createUrlFilters(schema);
  const f = filters.values;
  let chartType = $state<'line' | 'bar'>('line');
  let selectedPoint = $state<TrendPointSelectDetail | null>(null);

  const rangeError = $derived(validateRange({ from: f.from, to: f.to }, { today }));

  const insights = createQuery({
    key: () => ({ from: f.from, to: f.to, category: f.category, valid: !rangeError }),
    enabled: (k) => k.valid,
    fetch: (k, signal) => api.insights.me({ from: k.from, to: k.to, category: (k.category || undefined) as Category | undefined }, { signal }),
    debounce: 200,
  });
  const habits = createQuery({ key: () => 'all', fetch: (_k, signal) => api.habits.list({ size: 100, include_archived: true }, { signal }) });
  const earned = createQuery({ key: () => 'badges', fetch: (_k, signal) => api.insights.badges({ signal }) });
  const rules = createQuery({ key: () => 'rules', fetch: (_k, signal) => api.badgeRules.list({ signal }) });

  const series = $derived(insights.data ? personalDailySeries(insights.data) : []);
  const shares = $derived(insights.data ? categoryShares(insights.data.by_category) : []);
  const habitTitle = $derived(new Map((habits.data?.items ?? []).map((h) => [h.id, h])));
  const streakRows = $derived(
    [...(insights.data?.streaks ?? [])]
      .filter((s) => habitTitle.has(s.habit_id))
      .sort((a, b) => b.current - a.current || b.longest - a.longest),
  );
  const earnedCodes = $derived(new Set((earned.data ?? []).map((b) => b.code)));
  const lockedRules = $derived((rules.data ?? []).filter((r) => r.is_active && !earnedCodes.has(r.code)));
  const consistency = $derived(Math.round((insights.data?.totals.consistency_rate ?? 0) * 100));

  function describeRule(rule: { criterion: string; threshold: number; category: string | null }): string {
    if (rule.criterion === 'streak_days') return `Reach a ${rule.threshold}-day streak`;
    if (rule.criterion === 'category_completions') return `${rule.threshold} ${categoryLabel(rule.category).toLowerCase()} completions`;
    return `${rule.threshold} total completions`;
  }
</script>

<svelte:head>
  <title>My insights · TeamPulse</title>
</svelte:head>

<PageHeader title="My insights" description="Your personal trends, streaks and achievements. Only you can see this page's data." />

<form class="filters" aria-label="Insight filters" onsubmit={(e) => e.preventDefault()}>
  <DateRangePicker bind:from={f.from} bind:to={f.to} idPrefix="analytics-range" />
  <div class="field">
    <label for="analytics-category">Activity type</label>
    <select id="analytics-category" class="select" bind:value={f.category}>
      <option value="">All types</option>
      {#each CATEGORY_OPTIONS as option (option.value)}
        <option value={option.value}>{option.icon} {option.label}</option>
      {/each}
    </select>
  </div>
</form>

{#if rangeError}
  <EmptyState icon="📅" title="Adjust the date range" message={rangeError} />
{:else if insights.initialLoading}
  <Loading label="Crunching your numbers…" />
{:else if insights.error}
  <ErrorState error={insights.error} retry={insights.refetch} />
{:else if insights.data}
  {@const data = insights.data}
  <section class="grid-tiles" aria-label="Totals for {formatRange(data)}">
    <tp-stat-tile label="Completions" value={String(data.totals.completions)} hint={formatRange(data)}></tp-stat-tile>
    <tp-stat-tile label="Active days" value={String(data.totals.active_days)} hint="days with at least one completion"></tp-stat-tile>
    <tp-stat-tile label="Total value" value={String(data.totals.total_value)}></tp-stat-tile>
    <tp-stat-tile label="Consistency" value={percent(data.totals.consistency_rate)}></tp-stat-tile>
  </section>

  <div class="layout">
    <section class="card trend" aria-labelledby="trend-title">
      <div class="card-header">
        <h2 id="trend-title">Daily completions{f.category ? ` · ${categoryLabel(f.category)}` : ''}</h2>
        <div class="segmented" role="group" aria-label="Chart type">
          <button type="button" aria-pressed={chartType === 'line'} onclick={() => (chartType = 'line')}>Line</button>
          <button type="button" aria-pressed={chartType === 'bar'} onclick={() => (chartType = 'bar')}>Bars</button>
        </div>
      </div>
      <tp-trend-chart
        {series}
        type={chartType}
        height={260}
        yLabel="Completions"
        label="Your completions per day, {formatRange(data)}"
        showLegend={false}
        emptyText="No activity in this period."
        ontp-point-select={(e) => (selectedPoint = e.detail)}
      ></tp-trend-chart>
      {#if selectedPoint}
        <p class="small muted" role="status">
          {formatDate(selectedPoint.x)}: <strong>{selectedPoint.values[0]?.y ?? 0}</strong> completions.
        </p>
      {/if}
    </section>

    <section class="card consistency" aria-labelledby="consistency-title">
      <h2 id="consistency-title">Consistency</h2>
      <tp-progress-ring value={consistency} max={100} size={160} strokeWidth={14} tone={consistency >= 70 ? 'success' : consistency >= 40 ? 'warning' : 'danger'} label="Consistency rate">
        <div class="ring-center">
          <strong>{consistency}%</strong>
          <span class="xsmall muted">of days</span>
        </div>
      </tp-progress-ring>
      <p class="small muted">Share of days in the period on which you completed at least one habit.</p>
    </section>
  </div>

  <div class="layout-even">
    <section class="card" aria-labelledby="categories-title">
      <h2 id="categories-title" class="section-title">By activity type</h2>
      {#if shares.length === 0}
        <EmptyState icon="📊" title="No completions in this period" />
      {:else}
        <ul class="bar-list" aria-label="Completions by activity type">
          {#each shares as share (share.category)}
            <li>
              <span>{CATEGORY_META[share.category]?.icon} {categoryLabel(share.category)}</span>
              <span class="bar-track" role="presentation">
                <span class="bar-fill" style:width="{Math.max(2, share.share * 100)}%" style:background={CATEGORY_META[share.category]?.color}></span>
              </span>
              <span class="num small"><strong>{share.completions}</strong> <span class="sr-only">completions, {percent(share.share)}</span></span>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="card" aria-labelledby="streaks-title">
      <h2 id="streaks-title" class="section-title">Streaks</h2>
      {#if streakRows.length === 0}
        <EmptyState icon="🔥" title="No streaks yet" message="Complete habits on consecutive days or weeks to build one." />
      {:else}
        <div class="table-wrap">
          <table class="table">
            <caption class="sr-only">Streaks per habit</caption>
            <thead>
              <tr><th scope="col">Habit</th><th scope="col">Current</th><th scope="col">Longest</th><th scope="col">Total</th></tr>
            </thead>
            <tbody>
              {#each streakRows as s (s.habit_id)}
                <tr>
                  <td><a href="/habits/{s.habit_id}">{habitTitle.get(s.habit_id)?.title}</a></td>
                  <td class="num">{s.alive && s.current > 0 ? '🔥 ' : ''}{s.current} {s.frequency === 'weekly' ? 'wk' : 'd'}</td>
                  <td class="num">{s.longest}</td>
                  <td class="num">{s.total_completions}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </section>
  </div>
{/if}

<section class="card" id="badges" aria-labelledby="badges-title">
  <div class="card-header">
    <h2 id="badges-title">Badges</h2>
    <span class="small muted">{earned.data?.length ?? 0} earned · {lockedRules.length} to unlock</span>
  </div>
  {#if earned.initialLoading || rules.initialLoading}
    <Loading />
  {:else if earned.error}
    <ErrorState error={earned.error} retry={earned.refetch} />
  {:else}
    <div class="badges">
      {#each earned.data ?? [] as badge (badge.code)}
        <tp-badge icon={badge.icon} name={badge.name} description={badge.description} awardedAt={badge.awarded_at}></tp-badge>
      {/each}
      {#each lockedRules as rule (rule.code)}
        <tp-badge icon={rule.icon} name={rule.name} description={rule.description || describeRule(rule)} locked></tp-badge>
      {/each}
    </div>
    {#if (earned.data?.length ?? 0) === 0 && lockedRules.length === 0}
      <EmptyState icon="🎖️" title="No badges configured yet" />
    {/if}
  {/if}
</section>

<style>
  .layout {
    display: grid;
    gap: var(--tp-space-5);
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  }

  .layout-even {
    display: grid;
    gap: var(--tp-space-5);
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  @media (max-width: 960px) {
    .layout,
    .layout-even {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .consistency {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--tp-space-4);
    text-align: center;
  }

  .consistency h2 {
    align-self: flex-start;
  }

  .ring-center {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .ring-center strong {
    font-size: var(--tp-font-size-2xl);
  }

  .section-title {
    margin-bottom: var(--tp-space-4);
    font-size: var(--tp-font-size-lg);
  }

  .badges {
    display: grid;
    gap: var(--tp-space-3);
    grid-template-columns: repeat(auto-fill, minmax(9rem, 1fr));
  }

  .trend {
    min-width: 0;
  }
</style>
