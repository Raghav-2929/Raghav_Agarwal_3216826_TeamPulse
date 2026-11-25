<script lang="ts">
  import { goto } from '$app/navigation';
  import { api } from '$lib/api';
  import { errorMessage, isApiError } from '$lib/api/errors';
  import type { Category } from '$lib/api/types';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { CATEGORY_OPTIONS } from '$lib/utils/categories';
  import { addDays, diffDays, todayISO } from '$lib/utils/dates';
  import { hasErrors, validateChallenge, type FieldErrors } from '$lib/utils/validation';

  const today = todayISO();
  const teams = createQuery({ key: () => 'teams', fetch: (_k, signal) => api.teams.list({ signal }) });

  // Managers may only target a team they manage (or the whole organisation); admins any team.
  const teamOptions = $derived(
    (teams.data ?? []).filter((t) => session.isAdmin || session.managedTeamIds.includes(t.id) || t.manager_id === session.user?.id),
  );

  let form = $state({
    title: '',
    description: '',
    category: '',
    team_id: '',
    starts_on: today,
    ends_on: addDays(today, 29),
    target_count: 20,
  });
  let errors = $state<FieldErrors>({});
  let serverError = $state('');
  let submitting = $state(false);
  let formEl = $state<HTMLFormElement>();

  const durationDays = $derived(form.starts_on && form.ends_on ? diffDays(form.starts_on, form.ends_on) + 1 : 0);

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    serverError = '';
    errors = validateChallenge(form);
    if (form.team_id && !teamOptions.some((t) => t.id === form.team_id)) errors.team_id = 'You can only target a team you manage.';
    if (hasErrors(errors)) {
      queueMicrotask(() => formEl?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus());
      return;
    }
    submitting = true;
    try {
      const challenge = await api.challenges.create({
        title: form.title.trim(),
        description: form.description.trim() || null,
        category: (form.category || null) as Category | null,
        team_id: form.team_id || null,
        starts_on: form.starts_on,
        ends_on: form.ends_on,
        target_count: Number(form.target_count),
      });
      toasts.success(`Challenge “${challenge.title}” created.`);
      await goto(`/challenges/${challenge.id}`);
    } catch (error) {
      if (isApiError(error)) errors = { ...error.fieldErrors };
      serverError = errorMessage(error);
    } finally {
      submitting = false;
    }
  }

  const invalid = (field: string) => (errors[field] ? 'true' : undefined);
  const described = (field: string) => (errors[field] ? `challenge-${field}-error` : undefined);
</script>

<svelte:head>
  <title>New challenge · TeamPulse</title>
</svelte:head>

<PageHeader title="New challenge" description="Rally your team around a shared wellness goal." back={{ href: '/challenges', label: 'Challenges' }} />

{#if teams.error}
  <ErrorState error={teams.error} title="Could not load teams" retry={teams.refetch} />
{/if}

<form class="form card" bind:this={formEl} onsubmit={submit} novalidate aria-busy={submitting}>
  {#if serverError}<div class="form-error" role="alert">{serverError}</div>{/if}

  <div class="form-grid">
    <div class="field span-2">
      <label for="challenge-title">Title <span class="required" aria-hidden="true">*</span></label>
      <input id="challenge-title" class="input" bind:value={form.title} maxlength="120" required aria-invalid={invalid('title')} aria-describedby={described('title')} placeholder="e.g. November Step-Up" />
      {#if errors.title}<p id="challenge-title-error" class="field-error">{errors.title}</p>{/if}
    </div>

    <div class="field span-2">
      <label for="challenge-description">Description</label>
      <textarea id="challenge-description" class="textarea" bind:value={form.description} maxlength="1000" rows="3" aria-invalid={invalid('description')} aria-describedby={described('description')}></textarea>
      {#if errors.description}<p id="challenge-description-error" class="field-error">{errors.description}</p>{/if}
    </div>

    <div class="field">
      <label for="challenge-category">Activity type</label>
      <select id="challenge-category" class="select" bind:value={form.category} aria-describedby="challenge-category-hint">
        <option value="">Any activity type</option>
        {#each CATEGORY_OPTIONS as option (option.value)}
          <option value={option.value}>{option.icon} {option.label}</option>
        {/each}
      </select>
      <p id="challenge-category-hint" class="field-hint">Only completions of this type count towards the challenge.</p>
    </div>

    <div class="field">
      <label for="challenge-team">Who can join</label>
      <select id="challenge-team" class="select" bind:value={form.team_id} disabled={teams.initialLoading} aria-invalid={invalid('team_id')} aria-describedby={described('team_id')}>
        <option value="">🌐 Whole organisation</option>
        {#each teamOptions as team (team.id)}
          <option value={team.id}>👥 {team.name}</option>
        {/each}
      </select>
      {#if errors.team_id}<p id="challenge-team_id-error" class="field-error">{errors.team_id}</p>{/if}
    </div>

    <div class="field">
      <label for="challenge-start">Starts on <span class="required" aria-hidden="true">*</span></label>
      <input id="challenge-start" class="input" type="date" bind:value={form.starts_on} required aria-invalid={invalid('starts_on')} aria-describedby={described('starts_on')} />
      {#if errors.starts_on}<p id="challenge-starts_on-error" class="field-error">{errors.starts_on}</p>{/if}
    </div>

    <div class="field">
      <label for="challenge-end">Ends on <span class="required" aria-hidden="true">*</span></label>
      <input id="challenge-end" class="input" type="date" bind:value={form.ends_on} min={form.starts_on} required aria-invalid={invalid('ends_on')} aria-describedby={described('ends_on') ?? 'challenge-duration'} />
      <p id="challenge-duration" class="field-hint">{durationDays > 0 ? `${durationDays} days` : ''}</p>
      {#if errors.ends_on}<p id="challenge-ends_on-error" class="field-error">{errors.ends_on}</p>{/if}
    </div>

    <div class="field">
      <label for="challenge-target">Target completions <span class="required" aria-hidden="true">*</span></label>
      <input id="challenge-target" class="input" type="number" min="1" max="1000" step="1" bind:value={form.target_count} required aria-invalid={invalid('target_count')} aria-describedby={described('target_count')} />
      {#if errors.target_count}<p id="challenge-target_count-error" class="field-error">{errors.target_count}</p>{/if}
    </div>
  </div>

  <div class="form-actions">
    <a class="btn" href="/challenges">Cancel</a>
    <button type="submit" class="btn btn-primary" disabled={submitting}>{submitting ? 'Creating…' : 'Create challenge'}</button>
  </div>
</form>
