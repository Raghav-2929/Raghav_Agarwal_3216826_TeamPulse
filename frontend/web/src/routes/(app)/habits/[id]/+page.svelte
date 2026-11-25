<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { api } from '$lib/api';
  import { errorMessage, isApiError } from '$lib/api/errors';
  import CategoryPill from '$lib/components/CategoryPill.svelte';
  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { nextMilestone } from '$lib/utils/categories';
  import { addDays, formatDate, formatDateTime, todayISO } from '$lib/utils/dates';
  import { validateActivityNote } from '$lib/utils/validation';

  const BACKFILL_DAYS = 7;
  const HISTORY_SIZE = 10;
  const today = todayISO();

  const habitId = $derived(page.params.id ?? '');
  let historyPage = $state(1);

  const habit = createQuery({ key: () => habitId, fetch: (id, signal) => api.habits.get(id, { signal }) });
  const isOwner = $derived(!!habit.data && habit.data.owner_id === session.user?.id);

  // Activity logs and streaks are personal: only fetched for the owner.
  const history = createQuery({
    key: () => ({ id: habitId, page: historyPage, owner: isOwner }),
    enabled: (k) => k.owner,
    fetch: (k, signal) => api.activities.list({ habit_id: k.id, page: k.page, size: HISTORY_SIZE }, { signal }),
  });
  const todayLog = createQuery({
    key: () => ({ id: habitId, owner: isOwner }),
    enabled: (k) => k.owner,
    fetch: (k, signal) => api.activities.list({ habit_id: k.id, from: today, to: today, size: 1 }, { signal }),
  });
  const streaks = createQuery({
    key: () => isOwner,
    enabled: (owner) => owner,
    fetch: (_k, signal) => api.insights.streaks({ signal }),
  });

  let completedLocally = $state(false);
  let completing = $state(false);
  const doneToday = $derived(completedLocally || (todayLog.data?.items.length ?? 0) > 0);
  const streak = $derived(streaks.data?.find((s) => s.habit_id === habitId));
  const periodUnit = $derived(habit.data?.frequency === 'weekly' ? 'weeks' : 'days');

  // Back-fill form
  let logDate = $state(today);
  let logNote = $state('');
  let logError = $state('');
  let logging = $state(false);
  const noteError = $derived(validateActivityNote(logNote));

  let archiveOpen = $state(false);
  let archiving = $state(false);

  function afterLogged() {
    history.refetch();
    todayLog.refetch();
    streaks.refetch();
  }

  async function completeToday() {
    if (!habit.data) return;
    completing = true;
    try {
      await api.activities.create({ habit_id: habit.data.id, completed_on: today });
      completedLocally = true;
      toasts.success(`“${habit.data.title}” completed for today. Keep it up!`);
      afterLogged();
    } catch (error) {
      if (isApiError(error) && error.code === 'already_logged') {
        completedLocally = true;
        toasts.info('Already logged for today.');
      } else {
        toasts.error(error);
      }
    } finally {
      completing = false;
    }
  }

  async function logActivity(event: SubmitEvent) {
    event.preventDefault();
    if (!habit.data || noteError) return;
    logError = '';
    logging = true;
    try {
      await api.activities.create({ habit_id: habit.data.id, completed_on: logDate, note: logNote.trim() || undefined });
      if (logDate === today) completedLocally = true;
      toasts.success(`Logged for ${formatDate(logDate)}.`);
      logNote = '';
      afterLogged();
    } catch (error) {
      logError = isApiError(error) && error.code === 'already_logged' ? `Already logged for ${formatDate(logDate)}.` : errorMessage(error);
    } finally {
      logging = false;
    }
  }

  async function archive() {
    if (!habit.data) return;
    archiving = true;
    try {
      await api.habits.archive(habit.data.id);
      toasts.success(`“${habit.data.title}” archived.`);
      archiveOpen = false;
      await goto('/habits');
    } catch (error) {
      toasts.error(error);
    } finally {
      archiving = false;
    }
  }

  async function restore() {
    if (!habit.data) return;
    try {
      habit.set(await api.habits.update(habit.data.id, { is_archived: false }));
      toasts.success('Habit restored.');
    } catch (error) {
      toasts.error(error);
    }
  }
</script>

<svelte:head>
  <title>{habit.data?.title ?? 'Habit'} · TeamPulse</title>
</svelte:head>

{#if habit.initialLoading}
  <Loading label="Loading habit…" />
{:else if habit.error}
  <PageHeader title="Habit" back={{ href: '/habits', label: 'My habits' }} />
  <ErrorState
    error={habit.error}
    title={habit.error.status === 404 ? 'Habit not found' : 'Could not load this habit'}
    retry={habit.error.status === 404 ? undefined : habit.refetch}
  />
{:else if habit.data}
  {@const h = habit.data}
  <PageHeader title={h.title} description={h.description ?? undefined} back={isOwner ? { href: '/habits', label: 'My habits' } : { href: '/habits/team', label: 'Team habits' }}>
    {#snippet actions()}
      {#if isOwner}
        <a class="btn" href="/habits/{h.id}/edit">Edit</a>
        {#if h.is_archived}
          <button type="button" class="btn" onclick={restore}>Restore</button>
        {:else}
          <button type="button" class="btn" onclick={() => (archiveOpen = true)}>Archive</button>
        {/if}
      {/if}
    {/snippet}
  </PageHeader>

  <div class="layout">
    <section class="card summary" aria-labelledby="summary-title">
      <h2 id="summary-title" class="sr-only">Summary</h2>
      <dl class="kv">
        <dt>Activity type</dt>
        <dd><CategoryPill category={h.category} /></dd>
        <dt>Frequency</dt>
        <dd>{h.frequency === 'daily' ? 'Daily' : `${h.target_per_period}× per week`}</dd>
        <dt>Visibility</dt>
        <dd>{h.visibility === 'team' ? '🤝 Shared with team' : '🔒 Private'}</dd>
        <dt>Owner</dt>
        <dd>{isOwner ? 'You' : h.owner_name}</dd>
        <dt>Created</dt>
        <dd>{formatDate(h.created_at)}</dd>
        {#if h.is_archived}
          <dt>Status</dt>
          <dd><span class="pill">Archived</span></dd>
        {/if}
      </dl>

      {#if isOwner && !h.is_archived}
        <div class="today-action" data-testid="today-status">
          {#if todayLog.initialLoading}
            <Loading inline label="Checking today…" />
          {:else if doneToday}
            <p class="pill pill-success done" role="status">✓ Done today</p>
          {:else}
            <button type="button" class="btn btn-primary" onclick={completeToday} disabled={completing}>
              {completing ? 'Saving…' : 'Mark complete today'}
            </button>
          {/if}
        </div>
      {/if}
    </section>

    {#if isOwner}
      <section class="card streak" aria-labelledby="streak-title">
        <h2 id="streak-title">Streak</h2>
        {#if streaks.initialLoading}
          <Loading />
        {:else if streaks.error}
          <ErrorState error={streaks.error} retry={streaks.refetch} />
        {:else}
          <div class="streak-body">
            <tp-progress-ring
              value={streak?.current ?? 0}
              max={nextMilestone(streak?.current ?? 0)}
              size={128}
              strokeWidth={11}
              tone={h.category}
              label="Current streak towards next milestone"
            >
              <div class="ring-center">
                <strong>{streak?.current ?? 0}</strong>
                <span class="xsmall muted">{periodUnit}</span>
              </div>
            </tp-progress-ring>
            <dl class="kv">
              <dt>Current</dt>
              <dd>{streak?.current ?? 0} {periodUnit}{streak && !streak.alive ? ' (broken)' : ''}</dd>
              <dt>Longest</dt>
              <dd>{streak?.longest ?? 0} {periodUnit}</dd>
              <dt>Next milestone</dt>
              <dd>{nextMilestone(streak?.current ?? 0)} {periodUnit}</dd>
              <dt>Total completions</dt>
              <dd>{streak?.total_completions ?? 0}</dd>
            </dl>
          </div>
        {/if}
      </section>
    {/if}
  </div>

  {#if isOwner}
    <div class="layout">
      <section class="card" aria-labelledby="history-title">
        <div class="card-header">
          <h2 id="history-title">Activity history</h2>
        </div>
        {#if history.initialLoading}
          <Loading label="Loading history…" />
        {:else if history.error}
          <ErrorState error={history.error} retry={history.refetch} />
        {:else if (history.data?.items.length ?? 0) === 0}
          <EmptyState icon="🗓️" title="No activity yet" message="Completions you log will appear here." />
        {:else}
          <div class="table-wrap">
            <table class="table">
              <caption class="sr-only">Activity history for {h.title}</caption>
              <thead>
                <tr>
                  <th scope="col">Date</th>
                  <th scope="col">Value</th>
                  <th scope="col">Note</th>
                  <th scope="col">Logged at</th>
                </tr>
              </thead>
              <tbody>
                {#each history.data?.items ?? [] as activity (activity.id)}
                  <tr>
                    <td class="nowrap">{formatDate(activity.completed_on)}</td>
                    <td class="num">{activity.value}</td>
                    <td>{activity.note ?? '—'}</td>
                    <td class="nowrap small muted">{formatDateTime(activity.occurred_at)}</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
          <Pagination page={historyPage} size={HISTORY_SIZE} total={history.data?.total ?? 0} onchange={(p) => (historyPage = p)} label="History pages" />
        {/if}
      </section>

      {#if !h.is_archived}
        <section class="card" aria-labelledby="log-title">
          <h2 id="log-title">Log a completion</h2>
          <p class="small muted">Forgot to log? You can back-fill up to {BACKFILL_DAYS} days.</p>
          <form class="form log-form" onsubmit={logActivity} novalidate>
            {#if logError}<div class="form-error" role="alert">{logError}</div>{/if}
            <div class="field">
              <label for="log-date">Date</label>
              <input id="log-date" class="input" type="date" bind:value={logDate} min={addDays(today, -BACKFILL_DAYS)} max={today} required />
            </div>
            <div class="field">
              <label for="log-note">Note (optional)</label>
              <textarea
                id="log-note"
                class="textarea"
                bind:value={logNote}
                maxlength="280"
                rows="2"
                aria-invalid={noteError ? 'true' : undefined}
                aria-describedby="log-note-hint"
              ></textarea>
              <p id="log-note-hint" class="field-hint">{logNote.length}/280 · notes are private to you.</p>
              {#if noteError}<p class="field-error">{noteError}</p>{/if}
            </div>
            <div class="form-actions">
              <button type="submit" class="btn btn-primary" disabled={logging || !!noteError}>{logging ? 'Saving…' : 'Log completion'}</button>
            </div>
          </form>
        </section>
      {/if}
    </div>
  {:else}
    <div class="notice notice-info" role="note">
      <span class="notice-icon" aria-hidden="true">🛡️</span>
      <p>This is a teammate's shared habit. Activity logs and streaks are private to their owner and are never shown to others.</p>
    </div>
  {/if}

  <ConfirmDialog
    bind:open={archiveOpen}
    title="Archive habit?"
    message="“{h.title}” will be hidden from your dashboard. History and streaks are kept."
    confirmLabel="Archive"
    danger
    busy={archiving}
    onconfirm={archive}
  />
{/if}

<style>
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

  .summary,
  .streak {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-4);
  }

  .today-action {
    padding-top: var(--tp-space-4);
    border-top: 1px solid var(--tp-color-border);
  }

  .done {
    font-size: var(--tp-font-size-sm);
    padding: var(--tp-space-2) var(--tp-space-3);
  }

  .streak-body {
    display: flex;
    align-items: center;
    gap: var(--tp-space-6);
    flex-wrap: wrap;
  }

  .ring-center {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .ring-center strong {
    font-size: var(--tp-font-size-2xl);
  }

  .log-form {
    margin-top: var(--tp-space-3);
  }
</style>
