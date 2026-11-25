<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { api } from '$lib/api';
  import type { HabitCreate } from '$lib/api/types';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import HabitForm from '$lib/components/HabitForm.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { toasts } from '$lib/state/toasts.svelte';

  const habitId = $derived(page.params.id ?? '');
  const habit = createQuery({ key: () => habitId, fetch: (id, signal) => api.habits.get(id, { signal }) });
  const isOwner = $derived(!!habit.data && habit.data.owner_id === session.user?.id);

  async function save(values: HabitCreate) {
    const updated = await api.habits.update(habitId, values);
    toasts.success(`Saved changes to “${updated.title}”.`);
    await goto(`/habits/${updated.id}`);
  }
</script>

<svelte:head>
  <title>Edit habit · TeamPulse</title>
</svelte:head>

<PageHeader title="Edit habit" back={{ href: `/habits/${habitId}`, label: 'Back to habit' }} />

{#if habit.initialLoading}
  <Loading label="Loading habit…" />
{:else if habit.error}
  <ErrorState error={habit.error} title="Could not load this habit" retry={habit.refetch} />
{:else if habit.data && !isOwner}
  <ErrorState error={new Error('Only the owner can edit this habit.')} title="Read-only habit" />
{:else if habit.data}
  {#key habit.data.id}
    <HabitForm initial={habit.data} submitLabel="Save changes" onsubmit={save} oncancel={() => history.back()} />
  {/key}
{/if}
