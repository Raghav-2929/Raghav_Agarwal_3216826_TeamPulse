<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import type { HabitCreate } from '$lib/api/types';
  import HabitForm from '$lib/components/HabitForm.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { toasts } from '$lib/state/toasts.svelte';

  async function create(values: HabitCreate) {
    const habit = await api.habits.create(values);
    toasts.success(`Habit “${habit.title}” created.`);
    await goto(`/habits/${habit.id}`);
  }
</script>

<svelte:head>
  <title>New habit · TeamPulse</title>
</svelte:head>

<PageHeader title="New habit" description="Small, repeatable actions build lasting wellbeing." back={{ href: '/habits', label: 'My habits' }} />

<HabitForm submitLabel="Create habit" onsubmit={create} oncancel={() => history.back()} />
