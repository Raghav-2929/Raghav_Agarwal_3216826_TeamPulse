<script lang="ts">
  import { SvelteSet } from 'svelte/reactivity';
  import { api } from '$lib/api';
  import { isApiError } from '$lib/api/errors';
  import { CATEGORIES, VISIBILITIES, type Category, type HabitOut, type Visibility } from '$lib/api/types';
  import CategoryPill from '$lib/components/CategoryPill.svelte';
  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import SearchInput from '$lib/components/SearchInput.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { createUrlFilters } from '$lib/state/url-filters.svelte';
  import { CATEGORY_OPTIONS } from '$lib/utils/categories';
  import { todayISO } from '$lib/utils/dates';
  import { activeFilterCount, type FilterSchema } from '$lib/utils/filters';

  const PAGE_SIZE = 20;
  const schema = {
    search: { type: 'string', maxLength: 100 },
    category: { type: 'enum', values: CATEGORIES },
    visibility: { type: 'enum', values: VISIBILITIES },
    archived: { type: 'boolean' },
    page: { type: 'number', default: 1, min: 1 },
  } satisfies FilterSchema;

  // Filter state lives in the URL (?search=&category=&visibility=&archived=&page=).
  const filters = createUrlFilters(schema);
  const f = filters.values;
  const today = todayISO();

  const habits = createQuery({
    key: () => ({ search: f.search.trim(), category: f.category, visibility: f.visibility, archived: f.archived, page: f.page }),
    fetch: (k, signal) =>
      api.habits.list(
        {
          search: k.search || undefined,
          category: (k.category || undefined) as Category | undefined,
          visibility: (k.visibility || undefined) as Visibility | undefined,
          include_archived: k.archived,
          page: k.page,
          size: PAGE_SIZE,
        },
        { signal },
      ),
    debounce: 250,
  });

  const todayActivities = createQuery({
    key: () => today,
    fetch: (day, signal) => api.activities.list({ from: day, to: day, size: 100 }, { signal }),
  });

  const completedNow = new SvelteSet<string>();
  const doneIds = $derived(new Set([...(todayActivities.data?.items ?? []).map((a) => a.habit_id), ...completedNow]));
  const activeCount = $derived(activeFilterCount(schema, f, ['page']));
  let busy = $state<Record<string, boolean>>({});
  let archiveTarget = $state<HabitOut | null>(null);
  let archiveOpen = $state(false);
  let archiving = $state(false);

  function resetPage() {
    f.page = 1;
  }

  async function complete(habit: HabitOut) {
    busy[habit.id] = true;
    try {
      await api.activities.create({ habit_id: habit.id, completed_on: today });
      completedNow.add(habit.id);
      toasts.success(`“${habit.title}” completed for today.`);
    } catch (error) {
      if (isApiError(error) && error.code === 'already_logged') completedNow.add(habit.id);
      else toasts.error(error);
    } finally {
      busy[habit.id] = false;
    }
  }

  function askArchive(habit: HabitOut) {
    archiveTarget = habit;
    archiveOpen = true;
  }

  async function confirmArchive() {
    if (!archiveTarget) return;
    archiving = true;
    try {
      await api.habits.archive(archiveTarget.id);
      toasts.success(`“${archiveTarget.title}” archived.`);
      archiveOpen = false;
      habits.refetch();
    } catch (error) {
      toasts.error(error);
    } finally {
      archiving = false;
    }
  }

  async function restore(habit: HabitOut) {
    busy[habit.id] = true;
    try {
      await api.habits.update(habit.id, { is_archived: false });
      toasts.success(`“${habit.title}” restored.`);
      habits.refetch();
    } catch (error) {
      toasts.error(error);
    } finally {
      busy[habit.id] = false;
    }
  }
</script>

<svelte:head>
  <title>My habits · TeamPulse</title>
</svelte:head>

<PageHeader title="My habits" description="Create, track and organise your personal wellness habits.">
  {#snippet actions()}
    <a class="btn" href="/habits/team">Team habits</a>
    <a class="btn btn-primary" href="/habits/new">+ New habit</a>
  {/snippet}
</PageHeader>

<form class="filters" role="search" aria-label="Filter habits" onsubmit={(e) => e.preventDefault()}>
  <SearchInput id="habit-search" label="Search" placeholder="Search by title…" bind:value={f.search} oninput={resetPage} />
  <div class="field">
    <label for="habit-category">Activity type</label>
    <select id="habit-category" class="select" bind:value={f.category} onchange={resetPage}>
      <option value="">All types</option>
      {#each CATEGORY_OPTIONS as option (option.value)}
        <option value={option.value}>{option.icon} {option.label}</option>
      {/each}
    </select>
  </div>
  <div class="field">
    <label for="habit-visibility">Visibility</label>
    <select id="habit-visibility" class="select" bind:value={f.visibility} onchange={resetPage}>
      <option value="">Any visibility</option>
      <option value="private">Private</option>
      <option value="team">Team</option>
    </select>
  </div>
  <label class="checkbox">
    <input type="checkbox" bind:checked={f.archived} onchange={resetPage} />
    Show archived
  </label>
  {#if activeCount > 0}
    <button type="button" class="btn btn-ghost" onclick={() => filters.reset()}>Clear filters ({activeCount})</button>
  {/if}
</form>

<section aria-live="polite" aria-busy={habits.loading}>
  {#if habits.initialLoading}
    <Loading label="Loading habits…" />
  {:else if habits.error}
    <ErrorState error={habits.error} retry={habits.refetch} />
  {:else if (habits.data?.items.length ?? 0) === 0}
    {#if activeCount > 0}
      <EmptyState icon="🔎" title="No habits match these filters" message="Try a different search or clear the filters.">
        <button type="button" class="btn" onclick={() => filters.reset()}>Clear filters</button>
      </EmptyState>
    {:else}
      <EmptyState icon="🌱" title="You have no habits yet" message="Habits are small daily or weekly actions — a walk, a glass of water, ten minutes of reading.">
        <a class="btn btn-primary" href="/habits/new">Create your first habit</a>
      </EmptyState>
    {/if}
  {:else}
    <div class="table-wrap" class:stale={habits.loading}>
      <table class="table">
        <caption class="sr-only">My habits</caption>
        <thead>
          <tr>
            <th scope="col">Habit</th>
            <th scope="col">Activity type</th>
            <th scope="col">Frequency</th>
            <th scope="col">Visibility</th>
            <th scope="col">Today</th>
            <th scope="col" class="actions">Actions</th>
          </tr>
        </thead>
        <tbody>
          {#each habits.data?.items ?? [] as habit (habit.id)}
            {@const done = doneIds.has(habit.id)}
            <tr class:archived={habit.is_archived}>
              <td>
                <div class="habit">
                  <span class="dot" style:background={habit.color ?? 'var(--tp-color-primary)'} aria-hidden="true"></span>
                  <div>
                    <a href="/habits/{habit.id}" class="title">{habit.title}</a>
                    {#if habit.is_archived}<span class="pill">Archived</span>{/if}
                    {#if habit.description}<p class="xsmall muted desc">{habit.description}</p>{/if}
                  </div>
                </div>
              </td>
              <td><CategoryPill category={habit.category} /></td>
              <td class="nowrap">{habit.frequency === 'daily' ? 'Daily' : `${habit.target_per_period}× / week`}</td>
              <td>{habit.visibility === 'team' ? '🤝 Team' : '🔒 Private'}</td>
              <td>
                {#if habit.is_archived}
                  <span class="subtle small">—</span>
                {:else if done}
                  <span class="pill pill-success">✓ Done</span>
                {:else}
                  <button type="button" class="btn btn-sm btn-primary" disabled={busy[habit.id]} onclick={() => complete(habit)} aria-label="Mark {habit.title} complete for today">
                    {busy[habit.id] ? 'Saving…' : 'Complete'}
                  </button>
                {/if}
              </td>
              <td class="actions">
                <a class="btn btn-sm btn-ghost" href="/habits/{habit.id}/edit" aria-label="Edit {habit.title}">Edit</a>
                {#if habit.is_archived}
                  <button type="button" class="btn btn-sm btn-ghost" disabled={busy[habit.id]} onclick={() => restore(habit)}>Restore</button>
                {:else}
                  <button type="button" class="btn btn-sm btn-ghost" onclick={() => askArchive(habit)} aria-label="Archive {habit.title}">Archive</button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <Pagination page={f.page} size={PAGE_SIZE} total={habits.data?.total ?? 0} onchange={(p) => (f.page = p)} label="Habits pages" />
  {/if}
</section>

<ConfirmDialog
  bind:open={archiveOpen}
  title="Archive habit?"
  message="“{archiveTarget?.title}” will be hidden from your dashboard. Its history and streaks are kept and you can restore it later."
  confirmLabel="Archive"
  danger
  busy={archiving}
  onconfirm={confirmArchive}
/>

<style>
  .habit {
    display: flex;
    gap: var(--tp-space-3);
    align-items: flex-start;
  }

  .dot {
    flex: none;
    width: 0.75rem;
    height: 0.75rem;
    margin-top: 0.35rem;
    border-radius: 50%;
  }

  .title {
    font-weight: var(--tp-font-weight-semibold);
    color: var(--tp-color-text);
    text-decoration: none;
    margin-right: var(--tp-space-2);
  }

  .title:hover {
    text-decoration: underline;
  }

  .desc {
    max-width: 28rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  tr.archived {
    opacity: 0.7;
  }

  .stale {
    opacity: 0.6;
    transition: opacity var(--tp-duration-fast);
  }
</style>
