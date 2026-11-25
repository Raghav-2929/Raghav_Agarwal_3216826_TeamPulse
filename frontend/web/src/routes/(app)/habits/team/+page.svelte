<script lang="ts">
  import { api } from '$lib/api';
  import { CATEGORIES, type Category } from '$lib/api/types';
  import CategoryPill from '$lib/components/CategoryPill.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import SearchInput from '$lib/components/SearchInput.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { createUrlFilters } from '$lib/state/url-filters.svelte';
  import { CATEGORY_OPTIONS } from '$lib/utils/categories';
  import { activeFilterCount, type FilterSchema } from '$lib/utils/filters';

  const PAGE_SIZE = 24;
  const schema = {
    search: { type: 'string', maxLength: 100 },
    category: { type: 'enum', values: CATEGORIES },
    page: { type: 'number', default: 1, min: 1 },
  } satisfies FilterSchema;

  const filters = createUrlFilters(schema);
  const f = filters.values;

  const habits = createQuery({
    key: () => ({ search: f.search.trim(), category: f.category, page: f.page }),
    fetch: (k, signal) =>
      api.habits.team({ search: k.search || undefined, category: (k.category || undefined) as Category | undefined, page: k.page, size: PAGE_SIZE }, { signal }),
    debounce: 250,
  });

  const activeCount = $derived(activeFilterCount(schema, f, ['page']));
  const resetPage = () => (f.page = 1);
</script>

<svelte:head>
  <title>Team habits · TeamPulse</title>
</svelte:head>

<PageHeader
  title="Team habits"
  description="Habits your {session.user?.team_name ?? 'team'} teammates chose to share. Only the habit is shared — never anyone's activity log."
>
  {#snippet actions()}
    <a class="btn" href="/habits">My habits</a>
  {/snippet}
</PageHeader>

<form class="filters" role="search" aria-label="Filter team habits" onsubmit={(e) => e.preventDefault()}>
  <SearchInput id="team-habit-search" placeholder="Search shared habits…" bind:value={f.search} oninput={resetPage} />
  <div class="field">
    <label for="team-habit-category">Activity type</label>
    <select id="team-habit-category" class="select" bind:value={f.category} onchange={resetPage}>
      <option value="">All types</option>
      {#each CATEGORY_OPTIONS as option (option.value)}
        <option value={option.value}>{option.icon} {option.label}</option>
      {/each}
    </select>
  </div>
  {#if activeCount > 0}
    <button type="button" class="btn btn-ghost" onclick={() => filters.reset()}>Clear filters ({activeCount})</button>
  {/if}
</form>

<section aria-live="polite" aria-busy={habits.loading}>
  {#if !session.user?.team_id}
    <EmptyState icon="👥" title="You are not in a team yet" message="Ask an administrator to add you to a team to see shared habits." />
  {:else if habits.initialLoading}
    <Loading label="Loading team habits…" />
  {:else if habits.error}
    <ErrorState error={habits.error} retry={habits.refetch} />
  {:else if (habits.data?.items.length ?? 0) === 0}
    <EmptyState
      icon="🤝"
      title={activeCount ? 'No shared habits match these filters' : 'No shared habits yet'}
      message="Set a habit's visibility to “Team” to inspire your teammates."
    />
  {:else}
    <ul class="list-plain grid-cards">
      {#each habits.data?.items ?? [] as habit (habit.id)}
        <li>
          <a class="card card-link habit" href="/habits/{habit.id}">
            <span class="stripe" style:background={habit.color ?? 'var(--tp-color-primary)'} aria-hidden="true"></span>
            <strong class="title">{habit.title}</strong>
            {#if habit.description}<span class="small muted desc">{habit.description}</span>{/if}
            <span class="row meta">
              <CategoryPill category={habit.category} />
              <span class="pill">{habit.frequency === 'daily' ? 'Daily' : `${habit.target_per_period}× / week`}</span>
            </span>
            <span class="xsmall subtle">by {habit.owner_name}</span>
          </a>
        </li>
      {/each}
    </ul>
    <Pagination page={f.page} size={PAGE_SIZE} total={habits.data?.total ?? 0} onchange={(p) => (f.page = p)} />
  {/if}
</section>

<style>
  .habit {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-2);
    height: 100%;
    overflow: hidden;
  }

  /* The habit's colour as a soft wash in the card's top corner (behind the text). */
  .stripe {
    position: absolute;
    inset: 0;
    z-index: -1;
    opacity: 0.16;
    -webkit-mask-image: linear-gradient(155deg, #000, transparent 55%);
    mask-image: linear-gradient(155deg, #000, transparent 55%);
    pointer-events: none;
  }

  .title {
    font-size: var(--tp-font-size-md);
  }

  .desc {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .meta {
    gap: var(--tp-space-2);
  }
</style>
