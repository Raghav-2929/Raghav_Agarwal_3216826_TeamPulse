<script lang="ts">
  import { api } from '$lib/api';
  import { errorMessage, isApiError } from '$lib/api/errors';
  import type { TeamOut } from '$lib/api/types';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import Modal from '$lib/components/Modal.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { hasErrors, validateTeam, type FieldErrors } from '$lib/utils/validation';

  const teams = createQuery({ key: () => 'teams', fetch: (_k, signal) => api.teams.list({ signal }) });
  // Manager candidates: users with the manager role (admins can promote users on the Users page first).
  const managers = createQuery({ key: () => 'managers', fetch: (_k, signal) => api.users.list({ role: 'manager', size: 100 }, { signal }) });

  let open = $state(false);
  let editing = $state<TeamOut | null>(null);
  let form = $state({ name: '', description: '', manager_id: '' });
  let errors = $state<FieldErrors>({});
  let formError = $state('');
  let saving = $state(false);

  function openCreate() {
    editing = null;
    form = { name: '', description: '', manager_id: '' };
    errors = {};
    formError = '';
    open = true;
  }

  function openEdit(team: TeamOut) {
    editing = team;
    form = { name: team.name, description: team.description ?? '', manager_id: team.manager_id ?? '' };
    errors = {};
    formError = '';
    open = true;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    formError = '';
    errors = validateTeam(form);
    if (hasErrors(errors)) return;
    saving = true;
    const body = { name: form.name.trim(), description: form.description.trim() || null, manager_id: form.manager_id || null };
    try {
      const team = editing ? await api.teams.update(editing.id, body) : await api.teams.create(body);
      toasts.success(editing ? `Updated ${team.name}.` : `Created team ${team.name}.`);
      open = false;
      teams.refetch();
    } catch (error) {
      if (isApiError(error)) errors = { ...error.fieldErrors };
      formError = errorMessage(error);
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>Teams · Admin · TeamPulse</title>
</svelte:head>

<PageHeader title="Teams" description="Create teams and assign their managers. Managers only ever see aggregated data for their own teams.">
  {#snippet actions()}
    <button type="button" class="btn btn-primary" onclick={openCreate}>+ New team</button>
  {/snippet}
</PageHeader>

{#if teams.initialLoading}
  <Loading label="Loading teams…" />
{:else if teams.error}
  <ErrorState error={teams.error} retry={teams.refetch} />
{:else if (teams.data?.length ?? 0) === 0}
  <EmptyState icon="🏢" title="No teams yet" message="Create the first team to start grouping people.">
    <button type="button" class="btn btn-primary" onclick={openCreate}>Create team</button>
  </EmptyState>
{:else}
  <div class="table-wrap">
    <table class="table">
      <caption class="sr-only">Teams</caption>
      <thead>
        <tr>
          <th scope="col">Team</th>
          <th scope="col">Description</th>
          <th scope="col">Manager</th>
          <th scope="col">Members</th>
          <th scope="col" class="actions"><span class="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        {#each teams.data ?? [] as team (team.id)}
          <tr>
            <td><strong>{team.name}</strong></td>
            <td class="small muted">{team.description ?? '—'}</td>
            <td>{team.manager_name ?? '— unassigned —'}</td>
            <td class="num">{team.member_count}</td>
            <td class="actions"><button type="button" class="btn btn-sm" onclick={() => openEdit(team)} aria-label="Edit {team.name}">Edit</button></td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<Modal bind:open title={editing ? `Edit ${editing.name}` : 'New team'}>
  <form id="team-form" class="form" onsubmit={submit} novalidate>
    {#if formError}<div class="form-error" role="alert">{formError}</div>{/if}
    <div class="field">
      <label for="team-name">Name</label>
      <input id="team-name" class="input" bind:value={form.name} maxlength="80" aria-invalid={errors.name ? 'true' : undefined} aria-describedby={errors.name ? 'team-name-error' : undefined} />
      {#if errors.name}<p id="team-name-error" class="field-error">{errors.name}</p>{/if}
    </div>
    <div class="field">
      <label for="team-description">Description</label>
      <textarea id="team-description" class="textarea" bind:value={form.description} maxlength="500" rows="3"></textarea>
      {#if errors.description}<p class="field-error">{errors.description}</p>{/if}
    </div>
    <div class="field">
      <label for="team-manager">Manager</label>
      <select id="team-manager" class="select" bind:value={form.manager_id} aria-describedby="team-manager-hint">
        <option value="">No manager</option>
        {#each managers.data?.items ?? [] as manager (manager.id)}
          <option value={manager.id}>{manager.full_name}{manager.team_name ? ` (${manager.team_name})` : ''}</option>
        {/each}
      </select>
      <p id="team-manager-hint" class="field-hint">Only users with the Manager role are listed.</p>
      {#if managers.error}<p class="field-error">Could not load managers: {managers.error.detail}</p>{/if}
    </div>
  </form>
  {#snippet footer()}
    <button type="button" class="btn" onclick={() => (open = false)}>Cancel</button>
    <button type="submit" form="team-form" class="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : editing ? 'Save changes' : 'Create team'}</button>
  {/snippet}
</Modal>
