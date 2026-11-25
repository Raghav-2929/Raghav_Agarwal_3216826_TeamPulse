<script lang="ts">
  import { api } from '$lib/api';
  import { errorMessage, isApiError } from '$lib/api/errors';
  import { ROLES, type Role, type UserOut } from '$lib/api/types';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import Modal from '$lib/components/Modal.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import SearchInput from '$lib/components/SearchInput.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { createUrlFilters } from '$lib/state/url-filters.svelte';
  import { formatDate } from '$lib/utils/dates';
  import { activeFilterCount, type FilterSchema } from '$lib/utils/filters';
  import { ROLE_LABELS } from '$lib/utils/nav';
  import { hasErrors, validateFullName, validateNewUser, type FieldErrors } from '$lib/utils/validation';

  const PAGE_SIZE = 20;
  const schema = {
    search: { type: 'string', maxLength: 100 },
    role: { type: 'enum', values: ROLES },
    team: { type: 'string', maxLength: 64 },
    page: { type: 'number', default: 1, min: 1 },
  } satisfies FilterSchema;

  const filters = createUrlFilters(schema);
  const f = filters.values;

  const teams = createQuery({ key: () => 'teams', fetch: (_k, signal) => api.teams.list({ signal }) });
  const users = createQuery({
    key: () => ({ search: f.search.trim(), role: f.role, team: f.team, page: f.page }),
    fetch: (k, signal) =>
      api.users.list(
        { search: k.search || undefined, role: (k.role || undefined) as Role | undefined, team_id: k.team || undefined, page: k.page, size: PAGE_SIZE },
        { signal },
      ),
    debounce: 250,
  });

  const activeCount = $derived(activeFilterCount(schema, f, ['page']));
  const resetPage = () => (f.page = 1);

  // ---------------------------------------------------------------- create
  let createOpen = $state(false);
  let draft = $state({ email: '', full_name: '', password: '', role: 'employee', team_id: '' });
  let createErrors = $state<FieldErrors>({});
  let createError = $state('');
  let saving = $state(false);

  function openCreate() {
    draft = { email: '', full_name: '', password: '', role: 'employee', team_id: f.team || '' };
    createErrors = {};
    createError = '';
    createOpen = true;
  }

  async function submitCreate(event: SubmitEvent) {
    event.preventDefault();
    createError = '';
    createErrors = validateNewUser(draft);
    if (hasErrors(createErrors)) return;
    saving = true;
    try {
      const user = await api.users.create({
        email: draft.email.trim().toLowerCase(),
        full_name: draft.full_name.trim(),
        password: draft.password,
        role: draft.role as Role,
        team_id: draft.team_id || null,
      });
      toasts.success(`Created ${user.full_name}.`);
      createOpen = false;
      users.refetch();
      teams.refetch();
    } catch (error) {
      if (isApiError(error)) {
        createErrors = { ...error.fieldErrors };
        if (error.code === 'email_taken') createErrors.email = 'A user with this email already exists.';
      }
      createError = errorMessage(error);
    } finally {
      saving = false;
    }
  }

  // ---------------------------------------------------------------- edit
  let editOpen = $state(false);
  let editing = $state<UserOut | null>(null);
  let edit = $state({ full_name: '', role: 'employee', team_id: '', is_active: true });
  let editErrors = $state<FieldErrors>({});
  let editError = $state('');
  const editingSelf = $derived(editing?.id === session.user?.id);

  function openEdit(user: UserOut) {
    editing = user;
    edit = { full_name: user.full_name, role: user.role, team_id: user.team_id ?? '', is_active: user.is_active };
    editErrors = {};
    editError = '';
    editOpen = true;
  }

  async function submitEdit(event: SubmitEvent) {
    event.preventDefault();
    if (!editing) return;
    editError = '';
    const nameError = validateFullName(edit.full_name);
    editErrors = nameError ? { full_name: nameError } : {};
    if (hasErrors(editErrors)) return;
    saving = true;
    try {
      const updated = await api.users.update(editing.id, {
        full_name: edit.full_name.trim(),
        role: edit.role as Role,
        team_id: edit.team_id || null,
        is_active: edit.is_active,
      });
      toasts.success(`Updated ${updated.full_name}.`);
      if (updated.id === session.user?.id) session.setUser(updated);
      editOpen = false;
      users.refetch();
      teams.refetch();
    } catch (error) {
      if (isApiError(error)) editErrors = { ...error.fieldErrors };
      editError = errorMessage(error);
    } finally {
      saving = false;
    }
  }

  const roleTone = (role: Role) => (role === 'admin' ? 'pill-danger' : role === 'manager' ? 'pill-primary' : '');
</script>

<svelte:head>
  <title>Users · Admin · TeamPulse</title>
</svelte:head>

<PageHeader title="Users" description="Manage accounts, roles and team membership.">
  {#snippet actions()}
    <button type="button" class="btn btn-primary" onclick={openCreate}>+ New user</button>
  {/snippet}
</PageHeader>

<form class="filters" role="search" aria-label="Filter users" onsubmit={(e) => e.preventDefault()}>
  <SearchInput id="user-search" placeholder="Name or email…" bind:value={f.search} oninput={resetPage} />
  <div class="field">
    <label for="user-role">Role</label>
    <select id="user-role" class="select" bind:value={f.role} onchange={resetPage}>
      <option value="">All roles</option>
      {#each ROLES as role (role)}
        <option value={role}>{ROLE_LABELS[role]}</option>
      {/each}
    </select>
  </div>
  <div class="field">
    <label for="user-team">Team</label>
    <select id="user-team" class="select" bind:value={f.team} onchange={resetPage}>
      <option value="">All teams</option>
      {#each teams.data ?? [] as team (team.id)}
        <option value={team.id}>{team.name}</option>
      {/each}
    </select>
  </div>
  {#if activeCount > 0}
    <button type="button" class="btn btn-ghost" onclick={() => filters.reset()}>Clear filters ({activeCount})</button>
  {/if}
</form>

<section aria-live="polite" aria-busy={users.loading}>
  {#if users.initialLoading}
    <Loading label="Loading users…" />
  {:else if users.error}
    <ErrorState error={users.error} retry={users.refetch} />
  {:else if (users.data?.items.length ?? 0) === 0}
    <EmptyState icon="🧑‍💼" title="No users match these filters" />
  {:else}
    <div class="table-wrap">
      <table class="table">
        <caption class="sr-only">Users</caption>
        <thead>
          <tr>
            <th scope="col">Name</th>
            <th scope="col">Email</th>
            <th scope="col">Role</th>
            <th scope="col">Team</th>
            <th scope="col">Status</th>
            <th scope="col">Created</th>
            <th scope="col" class="actions"><span class="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody>
          {#each users.data?.items ?? [] as user (user.id)}
            <tr>
              <td><strong>{user.full_name}</strong>{#if user.id === session.user?.id} <span class="pill">You</span>{/if}</td>
              <td class="small">{user.email}</td>
              <td><span class="pill {roleTone(user.role)}">{ROLE_LABELS[user.role]}</span></td>
              <td>{user.team_name ?? '—'}</td>
              <td>{#if user.is_active}<span class="pill pill-success">Active</span>{:else}<span class="pill">Inactive</span>{/if}</td>
              <td class="small muted nowrap">{formatDate(user.created_at)}</td>
              <td class="actions"><button type="button" class="btn btn-sm" onclick={() => openEdit(user)} aria-label="Edit {user.full_name}">Edit</button></td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <Pagination page={f.page} size={PAGE_SIZE} total={users.data?.total ?? 0} onchange={(p) => (f.page = p)} label="User pages" />
  {/if}
</section>

<Modal bind:open={createOpen} title="New user" description="The user can sign in immediately with this password.">
  <form id="create-user" class="form" onsubmit={submitCreate} novalidate>
    {#if createError}<div class="form-error" role="alert">{createError}</div>{/if}
    <div class="field">
      <label for="new-email">Email</label>
      <input id="new-email" class="input" type="email" autocomplete="off" bind:value={draft.email} aria-invalid={createErrors.email ? 'true' : undefined} aria-describedby={createErrors.email ? 'new-email-error' : undefined} />
      {#if createErrors.email}<p id="new-email-error" class="field-error">{createErrors.email}</p>{/if}
    </div>
    <div class="field">
      <label for="new-name">Full name</label>
      <input id="new-name" class="input" autocomplete="off" bind:value={draft.full_name} aria-invalid={createErrors.full_name ? 'true' : undefined} aria-describedby={createErrors.full_name ? 'new-name-error' : undefined} />
      {#if createErrors.full_name}<p id="new-name-error" class="field-error">{createErrors.full_name}</p>{/if}
    </div>
    <div class="field">
      <label for="new-password">Initial password</label>
      <input id="new-password" class="input" type="password" autocomplete="new-password" bind:value={draft.password} aria-invalid={createErrors.password ? 'true' : undefined} aria-describedby="new-password-hint{createErrors.password ? ' new-password-error' : ''}" />
      <p id="new-password-hint" class="field-hint">At least 8 characters with upper-case, lower-case and a digit.</p>
      {#if createErrors.password}<p id="new-password-error" class="field-error">{createErrors.password}</p>{/if}
    </div>
    <div class="form-grid">
      <div class="field">
        <label for="new-role">Role</label>
        <select id="new-role" class="select" bind:value={draft.role}>
          {#each ROLES as role (role)}<option value={role}>{ROLE_LABELS[role]}</option>{/each}
        </select>
      </div>
      <div class="field">
        <label for="new-team">Team</label>
        <select id="new-team" class="select" bind:value={draft.team_id}>
          <option value="">No team</option>
          {#each teams.data ?? [] as team (team.id)}<option value={team.id}>{team.name}</option>{/each}
        </select>
      </div>
    </div>
  </form>
  {#snippet footer()}
    <button type="button" class="btn" onclick={() => (createOpen = false)}>Cancel</button>
    <button type="submit" form="create-user" class="btn btn-primary" disabled={saving}>{saving ? 'Creating…' : 'Create user'}</button>
  {/snippet}
</Modal>

<Modal bind:open={editOpen} title="Edit {editing?.full_name ?? 'user'}" description={editing?.email}>
  <form id="edit-user" class="form" onsubmit={submitEdit} novalidate>
    {#if editError}<div class="form-error" role="alert">{editError}</div>{/if}
    <div class="field">
      <label for="edit-name">Full name</label>
      <input id="edit-name" class="input" bind:value={edit.full_name} aria-invalid={editErrors.full_name ? 'true' : undefined} />
      {#if editErrors.full_name}<p class="field-error">{editErrors.full_name}</p>{/if}
    </div>
    <div class="form-grid">
      <div class="field">
        <label for="edit-role">Role</label>
        <select id="edit-role" class="select" bind:value={edit.role} disabled={editingSelf} aria-describedby={editingSelf ? 'edit-self-hint' : undefined}>
          {#each ROLES as role (role)}<option value={role}>{ROLE_LABELS[role]}</option>{/each}
        </select>
      </div>
      <div class="field">
        <label for="edit-team">Team</label>
        <select id="edit-team" class="select" bind:value={edit.team_id}>
          <option value="">No team</option>
          {#each teams.data ?? [] as team (team.id)}<option value={team.id}>{team.name}</option>{/each}
        </select>
      </div>
    </div>
    <label class="checkbox">
      <input type="checkbox" bind:checked={edit.is_active} disabled={editingSelf} />
      Account active (inactive users cannot sign in)
    </label>
    {#if editingSelf}<p id="edit-self-hint" class="field-hint">You cannot change your own role or deactivate yourself.</p>{/if}
  </form>
  {#snippet footer()}
    <button type="button" class="btn" onclick={() => (editOpen = false)}>Cancel</button>
    <button type="submit" form="edit-user" class="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</button>
  {/snippet}
</Modal>
