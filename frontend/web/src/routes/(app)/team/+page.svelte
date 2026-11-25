<script lang="ts">
  import { api } from '$lib/api';
  import { CATEGORIES, type Category } from '$lib/api/types';
  import DateRangePicker from '$lib/components/DateRangePicker.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { createUrlFilters } from '$lib/state/url-filters.svelte';
  import { CATEGORY_META, CATEGORY_OPTIONS, categoryLabel } from '$lib/utils/categories';
  import { formatDate, formatRange, presetRange, todayISO, validateRange } from '$lib/utils/dates';
  import type { FilterSchema } from '$lib/utils/filters';
  import { categoryShares, suppressedDays, suppressedLabel, teamDailySeries } from '$lib/utils/insights';
  import { ROLE_LABELS } from '$lib/utils/nav';

  const today = todayISO();
  const defaults = presetRange('30d', today);
  const schema = {
    team: { type: 'string', maxLength: 64 },
    from: { type: 'date', default: defaults.from },
    to: { type: 'date', default: defaults.to },
    category: { type: 'enum', values: CATEGORIES },
  } satisfies FilterSchema;

  const filters = createUrlFilters(schema);
  const f = filters.values;

  const teams = createQuery({ key: () => 'teams', fetch: (_k, signal) => api.teams.list({ signal }) });

  // Managers see the teams they manage (JWT `managed_team_ids`, falling back to `manager_id`); admins see all.
  const myTeams = $derived(
    (teams.data ?? []).filter((t) => session.isAdmin || session.managedTeamIds.includes(t.id) || t.manager_id === session.user?.id),
  );
  const teamId = $derived(myTeams.some((t) => t.id === f.team) ? f.team : (myTeams[0]?.id ?? ''));
  const team = $derived(myTeams.find((t) => t.id === teamId));
  const rangeError = $derived(validateRange({ from: f.from, to: f.to }, { today }));

  const insights = createQuery({
    key: () => ({ teamId, from: f.from, to: f.to, category: f.category, valid: !rangeError }),
    enabled: (k) => !!k.teamId && k.valid,
    fetch: (k, signal) => api.insights.team(k.teamId, { from: k.from, to: k.to, category: (k.category || undefined) as Category | undefined }, { signal }),
    debounce: 200,
  });
  const members = createQuery({
    key: () => teamId,
    enabled: (id) => !!id,
    fetch: (id, signal) => api.teams.members(id, { signal }),
  });

  const series = $derived(insights.data ? teamDailySeries(insights.data) : []);
  const hiddenDays = $derived(insights.data ? suppressedDays(insights.data) : []);
  const shares = $derived(insights.data ? categoryShares(insights.data.by_category) : []);
  const minCohort = $derived(insights.data?.min_cohort_size ?? 3);
  const gapLabel = $derived(suppressedLabel(minCohort));
</script>

<svelte:head>
  <title>Team insights · TeamPulse</title>
</svelte:head>

<PageHeader title="Team insights" description="Aggregated wellness trends for the teams you lead." />

<aside class="notice notice-info privacy" role="note" aria-labelledby="privacy-title" data-testid="privacy-notice">
  <span class="notice-icon" aria-hidden="true">🛡️</span>
  <div>
    <p id="privacy-title"><strong>Privacy notice: you are viewing aggregated team data only.</strong></p>
    <p class="small">
      Individual wellness data — who completed which habit, notes and personal streaks — is never shown to managers. Days on which
      fewer than {minCohort} members were active are suppressed entirely (shown as gaps), so no one's activity can be inferred.
    </p>
  </div>
</aside>

<form class="filters" aria-label="Team insight filters" onsubmit={(e) => e.preventDefault()}>
  <div class="field">
    <label for="team-select">Team</label>
    <select id="team-select" class="select" value={teamId} onchange={(e) => (f.team = e.currentTarget.value)} disabled={myTeams.length === 0}>
      {#each myTeams as t (t.id)}
        <option value={t.id}>{t.name}</option>
      {/each}
    </select>
  </div>
  <DateRangePicker bind:from={f.from} bind:to={f.to} idPrefix="team-range" />
  <div class="field">
    <label for="team-category">Activity type</label>
    <select id="team-category" class="select" bind:value={f.category}>
      <option value="">All types</option>
      {#each CATEGORY_OPTIONS as option (option.value)}
        <option value={option.value}>{option.icon} {option.label}</option>
      {/each}
    </select>
  </div>
</form>

{#if teams.initialLoading}
  <Loading label="Loading your teams…" />
{:else if teams.error}
  <ErrorState error={teams.error} retry={teams.refetch} />
{:else if myTeams.length === 0}
  <EmptyState icon="👥" title="You don't manage a team yet" message="Ask an administrator to assign you as a team manager." />
{:else if rangeError}
  <EmptyState icon="📅" title="Adjust the date range" message={rangeError} />
{:else if insights.initialLoading}
  <Loading label="Loading team trends…" />
{:else if insights.error}
  <ErrorState error={insights.error} title={insights.error.status === 403 ? 'You do not manage this team' : 'Could not load team insights'} retry={insights.refetch} />
{:else if insights.data}
  {@const data = insights.data}
  <section class="grid-tiles" aria-label="Team totals for {formatRange(data)}">
    <tp-stat-tile label="Team completions" value={String(data.totals.completions)} hint={formatRange(data)}></tp-stat-tile>
    <tp-stat-tile label="Active days" value={String(data.totals.active_days)} hint="reportable days with activity"></tp-stat-tile>
    <tp-stat-tile label="Avg active members" value={data.totals.avg_active_members.toFixed(1)} hint="per reportable day"></tp-stat-tile>
    <tp-stat-tile label="Suppressed days" value={String(data.totals.suppressed_days)} hint="fewer than {minCohort} active members"></tp-stat-tile>
  </section>

  <section class="card" aria-labelledby="team-trend-title" data-testid="team-trend">
    <div class="card-header">
      <h2 id="team-trend-title">{team?.name ?? 'Team'} · daily trend{f.category ? ` · ${categoryLabel(f.category)}` : ''}</h2>
      <span class="pill pill-info">Aggregated · k ≥ {minCohort}</span>
    </div>
    <tp-trend-chart
      {series}
      type="line"
      height={280}
      yLabel="Count"
      label="Aggregated team completions and active members per day, {formatRange(data)}"
      {gapLabel}
      emptyText="No reportable activity in this period."
    ></tp-trend-chart>
    {#if hiddenDays.length > 0}
      <details class="suppressed">
        <summary class="small">{hiddenDays.length} {hiddenDays.length === 1 ? 'day' : 'days'} suppressed for privacy</summary>
        <ul class="list-plain small">
          {#each hiddenDays as day (day)}
            <li>{formatDate(day)} — <span class="muted">suppressed (fewer than {minCohort} members)</span></li>
          {/each}
        </ul>
      </details>
    {/if}
  </section>

  <div class="layout">
    <section class="card" aria-labelledby="team-categories-title">
      <h2 id="team-categories-title" class="section-title">By activity type</h2>
      {#if shares.length === 0}
        <EmptyState icon="📊" title="No reportable completions in this period" />
      {:else}
        <ul class="bar-list" aria-label="Team completions by activity type">
          {#each shares as share (share.category)}
            <li>
              <span>{CATEGORY_META[share.category]?.icon} {categoryLabel(share.category)}</span>
              <span class="bar-track" role="presentation">
                <span class="bar-fill" style:width="{Math.max(2, share.share * 100)}%" style:background={CATEGORY_META[share.category]?.color}></span>
              </span>
              <span class="num small"><strong>{share.completions}</strong></span>
            </li>
          {/each}
        </ul>
      {/if}
      {#if data.suppressed_categories?.length}
        <p class="xsmall muted suppressed-cats">
          🛡️ Hidden for privacy (fewer than {minCohort} members): {data.suppressed_categories.map((c) => categoryLabel(c)).join(', ')}.
        </p>
      {/if}
    </section>

    <section class="card" aria-labelledby="members-title">
      <h2 id="members-title" class="section-title">Members{members.data ? ` (${members.data.length})` : ''}</h2>
      <p class="xsmall muted">Names only — no individual wellness data is available to managers.</p>
      {#if members.initialLoading}
        <Loading />
      {:else if members.error}
        <ErrorState error={members.error} retry={members.refetch} />
      {:else if (members.data?.length ?? 0) === 0}
        <EmptyState icon="👤" title="No members yet" />
      {:else}
        <ul class="list-plain members" data-testid="team-members">
          {#each members.data ?? [] as member (member.id)}
            <li><span class="member-name">{member.full_name}</span> <span class="pill">{ROLE_LABELS[member.role] ?? member.role}</span></li>
          {/each}
        </ul>
      {/if}
    </section>
  </div>
{/if}

<style>
  .privacy {
    box-shadow: inset 4px 0 0 var(--tp-color-info);
  }

  .layout {
    display: grid;
    gap: var(--tp-space-5);
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  @media (max-width: 900px) {
    .layout {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .section-title {
    margin-bottom: var(--tp-space-2);
    font-size: var(--tp-font-size-lg);
  }

  .suppressed {
    margin-top: var(--tp-space-4);
  }

  .suppressed-cats {
    margin-top: var(--tp-space-3);
  }

  .suppressed summary {
    cursor: pointer;
    color: var(--tp-color-text-muted);
  }

  .suppressed ul {
    margin-top: var(--tp-space-2);
    display: grid;
    gap: var(--tp-space-1);
  }

  .members {
    display: grid;
    gap: var(--tp-space-2);
    margin-top: var(--tp-space-3);
  }

  .members li {
    display: flex;
    justify-content: space-between;
    gap: var(--tp-space-2);
    padding: var(--tp-space-2) 0;
    border-bottom: 1px solid var(--tp-color-border);
    font-size: var(--tp-font-size-sm);
  }
</style>
