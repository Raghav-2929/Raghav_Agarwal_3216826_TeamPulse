<script lang="ts">
  import { api } from '$lib/api';
  import { CATEGORIES, CHALLENGE_STATUSES, type Category, type ChallengeStatus } from '$lib/api/types';
  import CategoryPill from '$lib/components/CategoryPill.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import SearchInput from '$lib/components/SearchInput.svelte';
  import StatusPill from '$lib/components/StatusPill.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { createUrlFilters } from '$lib/state/url-filters.svelte';
  import { CATEGORY_OPTIONS } from '$lib/utils/categories';
  import { formatDate, validateRange } from '$lib/utils/dates';
  import { activeFilterCount, type FilterSchema } from '$lib/utils/filters';

  const PAGE_SIZE = 12;
  const schema = {
    search: { type: 'string', maxLength: 100 },
    status: { type: 'enum', values: CHALLENGE_STATUSES },
    category: { type: 'enum', values: CATEGORIES },
    from: { type: 'date' },
    to: { type: 'date' },
    joined: { type: 'boolean' },
    page: { type: 'number', default: 1, min: 1 },
  } satisfies FilterSchema;

  // ?search=&status=&category=&from=&to=&joined=&page= — shareable, survives reloads.
  const filters = createUrlFilters(schema);
  const f = filters.values;

  const rangeError = $derived(
    f.from || f.to ? validateRange({ from: f.from || undefined, to: f.to || undefined }, { required: false, allowFuture: true, maxDays: 0 }) : null,
  );

  const challenges = createQuery({
    key: () => ({
      search: f.search.trim(),
      status: f.status,
      category: f.category,
      from: f.from,
      to: f.to,
      joined: f.joined,
      page: f.page,
      valid: !rangeError,
    }),
    enabled: (k) => k.valid,
    fetch: (k, signal) =>
      api.challenges.list(
        {
          search: k.search || undefined,
          status: (k.status || undefined) as ChallengeStatus | undefined,
          category: (k.category || undefined) as Category | undefined,
          from: k.from || undefined,
          to: k.to || undefined,
          joined: k.joined ? true : undefined,
          page: k.page,
          size: PAGE_SIZE,
        },
        { signal },
      ),
    debounce: 250,
  });

  const activeCount = $derived(activeFilterCount(schema, f, ['page']));
  const resetPage = () => (f.page = 1);
</script>

<svelte:head>
  <title>Challenges · TeamPulse</title>
</svelte:head>

<PageHeader title="Challenges" description="Team and organisation-wide challenges. Join one, log your habits and climb the leaderboard.">
  {#snippet actions()}
    {#if session.isLead}
      <a class="btn btn-primary" href="/challenges/new">+ New challenge</a>
    {/if}
  {/snippet}
</PageHeader>

<form class="filters" role="search" aria-label="Filter challenges" onsubmit={(e) => e.preventDefault()}>
  <SearchInput id="challenge-search" placeholder="Search challenges…" bind:value={f.search} oninput={resetPage} />
  <div class="field">
    <label for="challenge-status">Status</label>
    <select id="challenge-status" class="select" bind:value={f.status} onchange={resetPage}>
      <option value="">Any status</option>
      <option value="active">Active</option>
      <option value="upcoming">Upcoming</option>
      <option value="completed">Completed</option>
    </select>
  </div>
  <div class="field">
    <label for="challenge-category">Activity type</label>
    <select id="challenge-category" class="select" bind:value={f.category} onchange={resetPage}>
      <option value="">All types</option>
      {#each CATEGORY_OPTIONS as option (option.value)}
        <option value={option.value}>{option.icon} {option.label}</option>
      {/each}
    </select>
  </div>
  <div class="field">
    <label for="challenge-from">Running from</label>
    <input
      id="challenge-from"
      class="input"
      type="date"
      bind:value={f.from}
      max={f.to || undefined}
      onchange={resetPage}
      aria-invalid={rangeError ? 'true' : undefined}
      aria-describedby={rangeError ? 'challenge-range-error' : undefined}
    />
  </div>
  <div class="field">
    <label for="challenge-to">Running until</label>
    <input
      id="challenge-to"
      class="input"
      type="date"
      bind:value={f.to}
      min={f.from || undefined}
      onchange={resetPage}
      aria-invalid={rangeError ? 'true' : undefined}
      aria-describedby={rangeError ? 'challenge-range-error' : undefined}
    />
  </div>
  <label class="checkbox">
    <input type="checkbox" bind:checked={f.joined} onchange={resetPage} />
    Joined only
  </label>
  {#if activeCount > 0}
    <button type="button" class="btn btn-ghost" onclick={() => filters.reset()}>Clear filters ({activeCount})</button>
  {/if}
  {#if rangeError}
    <p id="challenge-range-error" class="field-error range-error" role="alert">{rangeError}</p>
  {/if}
</form>

<section aria-live="polite" aria-busy={challenges.loading}>
  {#if rangeError}
    <EmptyState icon="📅" title="Fix the date range" message={rangeError} />
  {:else if challenges.initialLoading}
    <Loading label="Loading challenges…" />
  {:else if challenges.error}
    <ErrorState error={challenges.error} retry={challenges.refetch} />
  {:else if (challenges.data?.items.length ?? 0) === 0}
    <EmptyState icon="🏆" title={activeCount ? 'No challenges match these filters' : 'No challenges yet'} message={activeCount ? 'Try widening your filters.' : 'Check back soon!'}>
      {#if activeCount}<button type="button" class="btn" onclick={() => filters.reset()}>Clear filters</button>{/if}
    </EmptyState>
  {:else}
    <ul class="list-plain grid-cards" class:stale={challenges.loading}>
      {#each challenges.data?.items ?? [] as challenge (challenge.id)}
        <li>
          <a class="card card-link challenge" href="/challenges/{challenge.id}">
            <div class="row-between top">
              <StatusPill status={challenge.status} />
              {#if challenge.joined}<span class="pill pill-primary">✓ Joined</span>{/if}
            </div>
            <div class="body">
              <div class="text">
                <h2 class="title">{challenge.title}</h2>
                <p class="xsmall muted">{formatDate(challenge.starts_on)} – {formatDate(challenge.ends_on)}</p>
              </div>
              {#if challenge.joined}
                <tp-progress-ring
                  value={challenge.my_score ?? 0}
                  max={challenge.target_count}
                  size={64}
                  strokeWidth={7}
                  tone={challenge.my_goal_reached ? 'success' : 'primary'}
                  label="My progress in {challenge.title}"
                ></tp-progress-ring>
              {/if}
            </div>
            <div class="row meta">
              <CategoryPill category={challenge.category} />
              <span class="pill">{challenge.team_name ? `👥 ${challenge.team_name}` : '🌐 Organisation-wide'}</span>
            </div>
            <p class="xsmall muted">
              Target {challenge.target_count} completions · {challenge.participant_count}
              {challenge.participant_count === 1 ? 'participant' : 'participants'}
            </p>
          </a>
        </li>
      {/each}
    </ul>
    <Pagination page={f.page} size={PAGE_SIZE} total={challenges.data?.total ?? 0} onchange={(p) => (f.page = p)} label="Challenge pages" />
  {/if}
</section>

<style>
  .challenge {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-3);
    height: 100%;
  }

  .body {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--tp-space-3);
  }

  .text {
    min-width: 0;
  }

  .title {
    font-size: var(--tp-font-size-lg);
    overflow-wrap: anywhere;
  }

  .meta {
    gap: var(--tp-space-2);
  }

  .range-error {
    flex-basis: 100%;
  }

  .stale {
    opacity: 0.6;
  }
</style>
