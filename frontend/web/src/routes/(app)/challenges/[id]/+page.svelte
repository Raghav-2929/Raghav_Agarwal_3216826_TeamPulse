<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import type { LeaderboardRowSelectDetail } from '@teampulse/ui-components';
  import { api } from '$lib/api';
  import { errorMessage, isApiError } from '$lib/api/errors';
  import type { ChallengeOut, LeaderboardIndividual, LeaderboardTeam } from '$lib/api/types';
  import CategoryPill from '$lib/components/CategoryPill.svelte';
  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import Modal from '$lib/components/Modal.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import StatusPill from '$lib/components/StatusPill.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { diffDays, formatDate, todayISO } from '$lib/utils/dates';
  import { hasErrors, validateChallenge, type FieldErrors } from '$lib/utils/validation';

  const challengeId = $derived(page.params.id ?? '');
  const challenge = createQuery({ key: () => challengeId, fetch: (id, signal) => api.challenges.get(id, { signal }) });
  const leaderboard = createQuery({ key: () => challengeId, fetch: (id, signal) => api.challenges.leaderboard(id, 20, { signal }) });

  let board = $state<'individual' | 'team'>('individual');
  let showOnLeaderboard = $state(true);
  let working = $state(false);
  let leaveOpen = $state(false);
  let deleteOpen = $state(false);
  let selected = $state<LeaderboardRowSelectDetail | null>(null);

  const c = $derived(challenge.data);
  const canManage = $derived(!!c && (session.isAdmin || c.created_by === session.user?.id));
  const canDelete = $derived(!!c && (session.isAdmin || (c.created_by === session.user?.id && c.status === 'upcoming')));
  const daysLeft = $derived(c ? Math.max(0, diffDays(todayISO(), c.ends_on)) : 0);
  const selectedLabel = $derived.by(() => {
    if (!selected) return '';
    if (selected.mode === 'team') {
      const t = selected.entry as LeaderboardTeam;
      return `#${t.rank} ${t.team_name}: ${t.total_score} total from ${t.participants} participants (avg ${t.average_score}).`;
    }
    const p = selected.entry as LeaderboardIndividual;
    return `#${p.rank} ${p.display_name}${p.team_name ? ` (${p.team_name})` : ''}: ${p.score} completions${p.goal_reached ? ' — goal reached 🎉' : ''}.`;
  });

  function showBoard(mode: 'individual' | 'team') {
    board = mode;
    selected = null;
  }

  function applyChallenge(updated: ChallengeOut) {
    challenge.set(updated);
    leaderboard.refetch();
  }

  async function join() {
    if (!c) return;
    working = true;
    try {
      applyChallenge(await api.challenges.join(c.id, showOnLeaderboard));
      toasts.success(`You joined “${c.title}”. Good luck!`);
    } catch (error) {
      if (isApiError(error) && error.code === 'already_joined') {
        challenge.refetch();
        toasts.info('You are already in this challenge.');
      } else {
        toasts.error(error);
      }
    } finally {
      working = false;
    }
  }

  async function toggleVisibility(event: Event) {
    if (!c) return;
    const value = (event.currentTarget as HTMLInputElement).checked;
    working = true;
    try {
      applyChallenge(await api.challenges.updateParticipation(c.id, value));
      toasts.success(value ? 'Your name is now shown on the leaderboard.' : 'You now appear as “Anonymous participant”.');
    } catch (error) {
      (event.currentTarget as HTMLInputElement).checked = !value;
      toasts.error(error);
    } finally {
      working = false;
    }
  }

  async function leave() {
    if (!c) return;
    working = true;
    try {
      await api.challenges.leave(c.id);
      leaveOpen = false;
      toasts.success(`You left “${c.title}”.`);
      challenge.refetch();
      leaderboard.refetch();
    } catch (error) {
      toasts.error(error);
    } finally {
      working = false;
    }
  }

  async function remove() {
    if (!c) return;
    working = true;
    try {
      await api.challenges.remove(c.id);
      toasts.success('Challenge deleted.');
      await goto('/challenges');
    } catch (error) {
      toasts.error(error);
    } finally {
      working = false;
      deleteOpen = false;
    }
  }

  // ---- edit (creator / admin)
  let editOpen = $state(false);
  let edit = $state({ title: '', description: '', starts_on: '', ends_on: '', target_count: 1 });
  let editErrors = $state<FieldErrors>({});
  let editError = $state('');

  function openEdit() {
    if (!c) return;
    edit = { title: c.title, description: c.description ?? '', starts_on: c.starts_on, ends_on: c.ends_on, target_count: c.target_count };
    editErrors = {};
    editError = '';
    editOpen = true;
  }

  async function saveEdit(event: SubmitEvent) {
    event.preventDefault();
    if (!c) return;
    editErrors = validateChallenge(edit);
    if (hasErrors(editErrors)) return;
    working = true;
    try {
      applyChallenge(
        await api.challenges.update(c.id, {
          title: edit.title.trim(),
          description: edit.description.trim() || null,
          ends_on: edit.ends_on,
          target_count: Number(edit.target_count),
        }),
      );
      editOpen = false;
      toasts.success('Challenge updated.');
    } catch (error) {
      if (isApiError(error)) editErrors = { ...error.fieldErrors };
      editError = errorMessage(error);
    } finally {
      working = false;
    }
  }
</script>

<svelte:head>
  <title>{c?.title ?? 'Challenge'} · TeamPulse</title>
</svelte:head>

{#if challenge.initialLoading}
  <Loading label="Loading challenge…" />
{:else if challenge.error}
  <PageHeader title="Challenge" back={{ href: '/challenges', label: 'Challenges' }} />
  <ErrorState error={challenge.error} title={challenge.error.status === 404 ? 'Challenge not found' : 'Could not load this challenge'} retry={challenge.refetch} />
{:else if c}
  <PageHeader title={c.title} description={c.description ?? undefined} back={{ href: '/challenges', label: 'Challenges' }}>
    {#snippet actions()}
      {#if canManage}<button type="button" class="btn" onclick={openEdit}>Edit</button>{/if}
      {#if canDelete}<button type="button" class="btn" onclick={() => (deleteOpen = true)}>Delete</button>{/if}
    {/snippet}
  </PageHeader>

  <div class="layout">
    <section class="card details" aria-labelledby="details-title">
      <h2 id="details-title" class="sr-only">Details</h2>
      <div class="row">
        <StatusPill status={c.status} />
        <CategoryPill category={c.category} />
        <span class="pill">{c.team_name ? `👥 ${c.team_name}` : '🌐 Organisation-wide'}</span>
      </div>
      <dl class="kv">
        <dt>Runs</dt>
        <dd>{formatDate(c.starts_on)} – {formatDate(c.ends_on)}</dd>
        {#if c.status === 'active'}
          <dt>Time left</dt>
          <dd>{daysLeft} {daysLeft === 1 ? 'day' : 'days'}</dd>
        {/if}
        <dt>Target</dt>
        <dd>{c.target_count} completions</dd>
        <dt>Participants</dt>
        <dd>{c.participant_count}</dd>
      </dl>

      <hr class="divider" />

      {#if c.joined}
        <div class="participation">
          <p class="pill pill-primary">✓ You are participating</p>
          <label class="checkbox">
            <input type="checkbox" checked={c.show_on_leaderboard ?? true} disabled={working} onchange={toggleVisibility} />
            Show my name on the leaderboard
          </label>
          <p class="xsmall muted">When off, you appear as “Anonymous participant”.</p>
          <button type="button" class="btn btn-sm" onclick={() => (leaveOpen = true)} disabled={working}>Leave challenge</button>
        </div>
      {:else if c.status === 'completed'}
        <p class="muted small">This challenge has ended.</p>
      {:else}
        <div class="participation">
          <label class="checkbox">
            <input type="checkbox" bind:checked={showOnLeaderboard} />
            Show me on the leaderboard
          </label>
          <p class="xsmall muted">Untick to take part anonymously.</p>
          <button type="button" class="btn btn-primary" onclick={join} disabled={working}>{working ? 'Joining…' : 'Join challenge'}</button>
        </div>
      {/if}
    </section>

    <section class="card progress" aria-labelledby="progress-title">
      <h2 id="progress-title">My progress</h2>
      {#if c.joined}
        <tp-progress-ring
          value={c.my_score ?? 0}
          max={c.target_count}
          size={168}
          strokeWidth={14}
          tone={c.my_goal_reached ? 'success' : (c.category ?? 'primary')}
          label="My progress towards the challenge target"
        >
          <div class="ring-center">
            <strong>{c.my_score ?? 0}</strong>
            <span class="xsmall muted">of {c.target_count}</span>
          </div>
        </tp-progress-ring>
        {#if c.my_goal_reached}
          <p class="pill pill-success">🎉 Goal reached!</p>
        {:else}
          <p class="small muted">{Math.max(0, c.target_count - (c.my_score ?? 0))} more to reach the goal.</p>
        {/if}
        {#if leaderboard.data?.my_rank}
          <p class="small">You are ranked <strong>#{leaderboard.data.my_rank}</strong>.</p>
        {/if}
      {:else}
        <p class="muted small">Join the challenge to track your progress here.</p>
      {/if}
    </section>
  </div>

  <section class="card" aria-labelledby="leaderboard-title">
    <div class="card-header">
      <h2 id="leaderboard-title">Leaderboard</h2>
      <div class="segmented" role="group" aria-label="Leaderboard type">
        <button type="button" aria-pressed={board === 'individual'} onclick={() => showBoard('individual')}>Individuals</button>
        <button type="button" aria-pressed={board === 'team'} onclick={() => showBoard('team')}>Teams</button>
      </div>
    </div>

    {#if leaderboard.initialLoading}
      <Loading label="Loading leaderboard…" />
    {:else if leaderboard.error}
      <ErrorState error={leaderboard.error} retry={leaderboard.refetch} />
    {:else if leaderboard.data}
      <tp-leaderboard-table
        mode={board}
        entries={board === 'team' ? leaderboard.data.teams : leaderboard.data.individuals}
        highlightMe={true}
        caption={board === 'team' ? `Team leaderboard for ${c.title}` : `Individual leaderboard for ${c.title}`}
        emptyText={board === 'team' ? 'No team scores yet.' : 'No participants yet — be the first to join!'}
        scoreLabel="Completions"
        ontp-row-select={(e) => (selected = e.detail)}
      >
        <span slot="caption">{board === 'team' ? 'Teams ranked by total completions' : 'Top participants'}</span>
        <button slot="actions" type="button" class="btn btn-ghost btn-sm" onclick={() => leaderboard.refetch()}>↻ Refresh</button>
      </tp-leaderboard-table>
      <p class="xsmall muted">Participants who opted out appear as “Anonymous participant”. Select a row for details.</p>
      {#if selected}
        <p class="notice selected" role="status" aria-live="polite">{selectedLabel}</p>
      {/if}
    {/if}
  </section>

  <ConfirmDialog
    bind:open={leaveOpen}
    title="Leave challenge?"
    message="Your progress in “{c.title}” will no longer count. You can re-join while it is running."
    confirmLabel="Leave"
    danger
    busy={working}
    onconfirm={leave}
  />
  <ConfirmDialog bind:open={deleteOpen} title="Delete challenge?" message="This permanently removes “{c.title}”." confirmLabel="Delete" danger busy={working} onconfirm={remove} />

  <Modal bind:open={editOpen} title="Edit challenge" size="md">
    <form id="edit-challenge" class="form" onsubmit={saveEdit} novalidate>
      {#if editError}<div class="form-error" role="alert">{editError}</div>{/if}
      <div class="field">
        <label for="edit-title">Title</label>
        <input id="edit-title" class="input" bind:value={edit.title} maxlength="120" aria-invalid={editErrors.title ? 'true' : undefined} />
        {#if editErrors.title}<p class="field-error">{editErrors.title}</p>{/if}
      </div>
      <div class="field">
        <label for="edit-description">Description</label>
        <textarea id="edit-description" class="textarea" bind:value={edit.description} maxlength="1000" rows="3"></textarea>
      </div>
      <div class="form-grid">
        <div class="field">
          <label for="edit-end">Ends on</label>
          <input id="edit-end" class="input" type="date" bind:value={edit.ends_on} min={edit.starts_on} aria-invalid={editErrors.ends_on ? 'true' : undefined} />
          {#if editErrors.ends_on}<p class="field-error">{editErrors.ends_on}</p>{/if}
        </div>
        <div class="field">
          <label for="edit-target">Target completions</label>
          <input id="edit-target" class="input" type="number" min="1" max="1000" bind:value={edit.target_count} aria-invalid={editErrors.target_count ? 'true' : undefined} />
          {#if editErrors.target_count}<p class="field-error">{editErrors.target_count}</p>{/if}
        </div>
      </div>
    </form>
    {#snippet footer()}
      <button type="button" class="btn" onclick={() => (editOpen = false)}>Cancel</button>
      <button type="submit" form="edit-challenge" class="btn btn-primary" disabled={working}>{working ? 'Saving…' : 'Save'}</button>
    {/snippet}
  </Modal>
{/if}

<style>
  .layout {
    display: grid;
    gap: var(--tp-space-5);
    grid-template-columns: minmax(0, 3fr) minmax(0, 2fr);
  }

  @media (max-width: 900px) {
    .layout {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .details,
  .progress {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-4);
  }

  .progress {
    align-items: center;
    text-align: center;
  }

  .progress h2 {
    align-self: flex-start;
  }

  .participation {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--tp-space-2);
  }

  .ring-center {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .ring-center strong {
    font-size: var(--tp-font-size-3xl);
  }

  .selected {
    margin-top: var(--tp-space-3);
  }
</style>
