<script lang="ts">
  import { api } from '$lib/api';
  import { errorMessage } from '$lib/api/errors';
  import type { NotificationOut, NotificationPreferences } from '$lib/api/types';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import Pagination from '$lib/components/Pagination.svelte';
  import { notifications } from '$lib/state/notifications.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { createUrlFilters } from '$lib/state/url-filters.svelte';
  import { formatDateTime, pad2, relativeTime } from '$lib/utils/dates';
  import type { FilterSchema } from '$lib/utils/filters';
  import { validateReminderHour } from '$lib/utils/validation';

  const PAGE_SIZE = 15;
  const ICONS: Record<string, string> = {
    welcome: '👋',
    reminder: '⏰',
    'badge.awarded': '🎖️',
    'streak.milestone': '🔥',
    'challenge.created': '🏆',
    'challenge.joined': '🤝',
    'challenge.goal_reached': '🎉',
  };

  const schema = {
    unread: { type: 'boolean' },
    page: { type: 'number', default: 1, min: 1 },
  } satisfies FilterSchema;
  const filters = createUrlFilters(schema, { debounce: 0 });
  const f = filters.values;

  const list = createQuery({
    key: () => ({ unread: f.unread, page: f.page }),
    fetch: (k, signal) => api.notifications.list({ unread_only: k.unread, page: k.page, size: PAGE_SIZE }, { signal }),
  });

  let marking = $state<Record<string, boolean>>({});
  let markingAll = $state(false);

  function link(n: NotificationOut): string | null {
    const data = n.data ?? {};
    if (typeof data.challenge_id === 'string') return `/challenges/${data.challenge_id}`;
    if (typeof data.habit_id === 'string') return `/habits/${data.habit_id}`;
    if (n.type === 'badge.awarded') return '/analytics#badges';
    return null;
  }

  async function markRead(n: NotificationOut) {
    marking[n.id] = true;
    try {
      const updated = await api.notifications.markRead(n.id);
      if (list.data) list.set({ ...list.data, items: list.data.items.map((i) => (i.id === n.id ? { ...i, ...updated, is_read: true } : i)) });
      notifications.markedRead();
      if (f.unread) list.refetch();
    } catch (error) {
      toasts.error(error);
    } finally {
      marking[n.id] = false;
    }
  }

  async function markAll() {
    markingAll = true;
    try {
      const { updated } = await api.notifications.markAllRead();
      notifications.reset();
      toasts.success(updated ? `Marked ${updated} notification${updated === 1 ? '' : 's'} as read.` : 'Everything is already read.');
      list.refetch();
    } catch (error) {
      toasts.error(error);
    } finally {
      markingAll = false;
    }
  }

  // ---------------------------------------------------------------- preferences
  const prefsQuery = createQuery({ key: () => 'prefs', fetch: (_k, signal) => api.notifications.preferences({ signal }) });
  let prefs = $state<NotificationPreferences | null>(null);
  let prefsSaving = $state(false);
  let prefsError = $state('');

  $effect(() => {
    if (prefsQuery.data && !prefs) prefs = { ...prefsQuery.data };
  });

  const browserTz = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  const timezones = $derived.by(() => {
    let zones: string[] = [];
    try {
      zones = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf?.('timeZone') ?? [];
    } catch {
      zones = [];
    }
    const extra = [browserTz, 'UTC', prefs?.timezone].filter((z): z is string => !!z);
    return Array.from(new Set([...extra, ...zones])).sort((a, b) => (a === 'UTC' ? -1 : b === 'UTC' ? 1 : a.localeCompare(b)));
  });
  const hourError = $derived(prefs ? validateReminderHour(Number(prefs.reminder_hour)) : null);

  async function savePrefs(event: SubmitEvent) {
    event.preventDefault();
    if (!prefs || hourError) return;
    prefsSaving = true;
    prefsError = '';
    try {
      const saved = await api.notifications.updatePreferences({
        reminders_enabled: prefs.reminders_enabled,
        reminder_hour: Number(prefs.reminder_hour),
        timezone: prefs.timezone,
        email_enabled: prefs.email_enabled,
      });
      if (saved) prefs = { ...saved };
      toasts.success('Notification preferences saved.');
    } catch (error) {
      prefsError = errorMessage(error);
    } finally {
      prefsSaving = false;
    }
  }
</script>

<svelte:head>
  <title>Notifications · TeamPulse</title>
</svelte:head>

<PageHeader title="Notifications" description="Badges, streak milestones, reminders and challenge updates.">
  {#snippet actions()}
    <button type="button" class="btn" onclick={markAll} disabled={markingAll || notifications.unread === 0}>
      {markingAll ? 'Marking…' : 'Mark all as read'}
    </button>
  {/snippet}
</PageHeader>

<div class="layout">
  <section aria-labelledby="inbox-title" class="stack">
    <div class="row-between">
      <h2 id="inbox-title" class="sr-only">Inbox</h2>
      <div class="segmented" role="group" aria-label="Filter notifications">
        <button type="button" aria-pressed={!f.unread} onclick={() => filters.patch({ unread: false, page: 1 })}>All</button>
        <button type="button" aria-pressed={f.unread} onclick={() => filters.patch({ unread: true, page: 1 })}>
          Unread{notifications.unread ? ` (${notifications.unread})` : ''}
        </button>
      </div>
    </div>

    {#if list.initialLoading}
      <Loading label="Loading notifications…" />
    {:else if list.error}
      <ErrorState error={list.error} retry={list.refetch} />
    {:else if (list.data?.items.length ?? 0) === 0}
      <EmptyState icon="📭" title={f.unread ? 'No unread notifications' : 'No notifications yet'} message={f.unread ? 'You are all caught up!' : undefined} />
    {:else}
      <ul class="list-plain items" aria-busy={list.loading}>
        {#each list.data?.items ?? [] as n (n.id)}
          {@const href = link(n)}
          <li class="item card" class:unread={!n.is_read}>
            <span class="icon" aria-hidden="true">{ICONS[n.type] ?? '🔔'}</span>
            <div class="body">
              <p class="title">
                {#if !n.is_read}<span class="sr-only">Unread: </span>{/if}
                {#if href}<a {href}>{n.title}</a>{:else}{n.title}{/if}
              </p>
              {#if n.body}<p class="small muted">{n.body}</p>{/if}
              <p class="xsmall subtle"><time datetime={n.created_at} title={formatDateTime(n.created_at)}>{relativeTime(n.created_at)}</time></p>
            </div>
            {#if !n.is_read}
              <button type="button" class="btn btn-sm btn-ghost" onclick={() => markRead(n)} disabled={marking[n.id]} aria-label="Mark “{n.title}” as read">Mark read</button>
            {/if}
          </li>
        {/each}
      </ul>
      <Pagination page={f.page} size={PAGE_SIZE} total={list.data?.total ?? 0} onchange={(p) => (f.page = p)} label="Notification pages" />
    {/if}
  </section>

  <section class="card prefs" aria-labelledby="prefs-title">
    <h2 id="prefs-title">Preferences</h2>
    {#if prefsQuery.initialLoading}
      <Loading />
    {:else if prefsQuery.error}
      <ErrorState error={prefsQuery.error} retry={prefsQuery.refetch} />
    {:else if prefs}
      <form class="form" onsubmit={savePrefs} novalidate>
        {#if prefsError}<div class="form-error" role="alert">{prefsError}</div>{/if}
        <label class="checkbox"><input type="checkbox" bind:checked={prefs.reminders_enabled} /> Daily habit reminders</label>
        <div class="field">
          <label for="pref-hour">Reminder time</label>
          <select id="pref-hour" class="select" bind:value={prefs.reminder_hour} disabled={!prefs.reminders_enabled} aria-invalid={hourError ? 'true' : undefined}>
            {#each Array.from({ length: 24 }, (_, h) => h) as hour (hour)}
              <option value={hour}>{pad2(hour)}:00</option>
            {/each}
          </select>
          {#if hourError}<p class="field-error">{hourError}</p>{/if}
        </div>
        <div class="field">
          <label for="pref-tz">Time zone</label>
          <select id="pref-tz" class="select" bind:value={prefs.timezone}>
            {#each timezones as tz (tz)}
              <option value={tz}>{tz}</option>
            {/each}
          </select>
          {#if prefs.timezone !== browserTz}
            <button type="button" class="btn btn-ghost btn-sm tz" onclick={() => prefs && (prefs.timezone = browserTz)}>Use my current time zone ({browserTz})</button>
          {/if}
        </div>
        <label class="checkbox"><input type="checkbox" bind:checked={prefs.email_enabled} /> Also send notifications by email</label>
        <div class="form-actions">
          <button type="submit" class="btn btn-primary" disabled={prefsSaving}>{prefsSaving ? 'Saving…' : 'Save preferences'}</button>
        </div>
      </form>
    {/if}
  </section>
</div>

<style>
  .layout {
    display: grid;
    gap: var(--tp-space-5);
    grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
    align-items: start;
  }

  @media (max-width: 960px) {
    .layout {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .items {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-2);
  }

  .item {
    display: flex;
    gap: var(--tp-space-3);
    align-items: flex-start;
    padding: var(--tp-space-4);
  }

  .item.unread {
    background:
      linear-gradient(100deg, color-mix(in srgb, var(--tp-color-primary) 9%, transparent), transparent 55%),
      var(--tp-glass-bg);
  }

  /* Unread marker: a small blue dot on the icon. */
  .unread .icon::after {
    content: '';
    position: absolute;
    top: -3px;
    right: -3px;
    width: 0.7rem;
    height: 0.7rem;
    border-radius: 50%;
    background: var(--tp-color-primary);
    box-shadow: 0 0 0 2px var(--tp-color-surface);
  }

  .icon {
    position: relative;
    display: grid;
    place-items: center;
    flex: none;
    width: 2.75rem;
    height: 2.75rem;
    border-radius: var(--tp-radius-md);
    background: var(--tp-glass-bg-strong);
    border: 1px solid var(--tp-glass-border);
    box-shadow: var(--tp-shadow-sm);
    font-size: 1.3rem;
  }

  .body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .title {
    font-weight: var(--tp-font-weight-semibold);
  }

  .unread .title {
    font-weight: var(--tp-font-weight-bold);
  }

  .prefs h2 {
    font-size: var(--tp-font-size-lg);
    margin-bottom: var(--tp-space-4);
  }

  .tz {
    align-self: flex-start;
  }
</style>
