<script lang="ts">
  import { SvelteSet } from 'svelte/reactivity';
  import { api } from '$lib/api';
  import { isApiError } from '$lib/api/errors';
  import type { HabitOut, Streak } from '$lib/api/types';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { session } from '$lib/state/session.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { nextMilestone } from '$lib/utils/categories';
  import { addDays, formatDate, todayISO } from '$lib/utils/dates';
  import { percent, personalDailySeries, suppressedLabel, teamDailySeries } from '$lib/utils/insights';

  const today = todayISO();
  const trendFrom = addDays(today, -13);

  const habits = createQuery({ key: () => 'habits', fetch: (_k, signal) => api.habits.list({ size: 100 }, { signal }) });
  const todayActivities = createQuery({
    key: () => today,
    fetch: (day, signal) => api.activities.list({ from: day, to: day, size: 100 }, { signal }),
  });
  const streaks = createQuery({ key: () => 'streaks', fetch: (_k, signal) => api.insights.streaks({ signal }) });
  const challenges = createQuery({
    key: () => 'joined-active',
    fetch: (_k, signal) => api.challenges.list({ joined: true, status: 'active', size: 6 }, { signal }),
  });
  const badges = createQuery({ key: () => 'badges', fetch: (_k, signal) => api.insights.badges({ signal }) });
  const insights = createQuery({
    key: () => ({ from: trendFrom, to: today }),
    fetch: (range, signal) => api.insights.me(range, { signal }),
  });

  // Managers: aggregated snapshot of the first managed team (admins open /team to pick one).
  const snapshotTeamId = $derived(session.isManager ? (session.managedTeamIds[0] ?? null) : null);
  const teamSnapshot = createQuery({
    key: () => snapshotTeamId,
    enabled: (teamId) => !!teamId,
    fetch: (teamId, signal) => api.insights.team(teamId as string, { from: trendFrom, to: today }, { signal }),
  });

  const completedToday = new SvelteSet<string>();
  let busy = $state<Record<string, boolean>>({});

  const activeHabits = $derived((habits.data?.items ?? []).filter((h) => !h.is_archived));
  const streakByHabit = $derived(new Map<string, Streak>((streaks.data ?? []).map((s) => [s.habit_id, s])));
  const doneIds = $derived(new Set([...(todayActivities.data?.items ?? []).map((a) => a.habit_id), ...completedToday]));
  const doneCount = $derived(activeHabits.filter((h) => doneIds.has(h.id)).length);
  const topStreaks = $derived(
    (streaks.data ?? [])
      .filter((s) => s.current > 0)
      .sort((a, b) => b.current - a.current)
      .slice(0, 3)
      .map((s) => ({ streak: s, habit: activeHabits.find((h) => h.id === s.habit_id) }))
      .filter((x): x is { streak: Streak; habit: HabitOut } => !!x.habit),
  );
  const bestStreak = $derived(Math.max(0, ...(streaks.data ?? []).map((s) => s.current)));
  const recentBadges = $derived([...(badges.data ?? [])].sort((a, b) => b.awarded_at.localeCompare(a.awarded_at)).slice(0, 4));
  const trend = $derived(insights.data ? personalDailySeries(insights.data) : []);
  const teamTrend = $derived(teamSnapshot.data ? teamDailySeries(teamSnapshot.data) : []);
  const greeting = $derived.by(() => {
    const hour = new Date().getHours();
    return hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  });
  const firstName = $derived(session.user?.full_name.split(' ')[0] ?? '');

  async function complete(habit: HabitOut) {
    if (busy[habit.id] || doneIds.has(habit.id)) return;
    busy[habit.id] = true;
    try {
      await api.activities.create({ habit_id: habit.id, completed_on: today });
      completedToday.add(habit.id);
      toasts.success(`Nice work! “${habit.title}” is done for today.`);
      streaks.refetch();
      insights.refetch();
    } catch (error) {
      if (isApiError(error) && error.code === 'already_logged') {
        completedToday.add(habit.id);
        toasts.info(`“${habit.title}” was already logged today.`);
      } else {
        toasts.error(error);
      }
    } finally {
      busy[habit.id] = false;
    }
  }
</script>

<svelte:head>
  <title>Dashboard · TeamPulse</title>
</svelte:head>

<PageHeader title="{greeting}, {firstName} 👋" description="Here is how your wellness habits are going today, {formatDate(today)}.">
  {#snippet actions()}
    <a class="btn" href="/challenges">Browse challenges</a>
    <a class="btn btn-primary" href="/habits/new">+ New habit</a>
  {/snippet}
</PageHeader>

<!-- KPI tiles -->
<section class="grid-tiles" aria-label="Key figures">
  <tp-stat-tile style="--tp-tile-accent: var(--tp-color-success)" label="Done today" value={habits.data ? `${doneCount}/${activeHabits.length}` : '…'} hint="habits completed"></tp-stat-tile>
  <tp-stat-tile style="--tp-tile-accent: var(--tp-chart-1)" label="Completions" value={insights.data ? String(insights.data.totals.completions) : '…'} hint="last 14 days"></tp-stat-tile>
  <tp-stat-tile style="--tp-tile-accent: var(--tp-chart-5)" label="Consistency" value={insights.data ? percent(insights.data.totals.consistency_rate) : '…'} hint="of days with activity"></tp-stat-tile>
  <tp-stat-tile style="--tp-tile-accent: var(--tp-chart-3)" label="Best streak" value={streaks.data ? `${bestStreak}` : '…'} hint="current, in periods"></tp-stat-tile>
</section>

<div class="layout">
  <!-- Today's habits -->
  <section class="card today" aria-labelledby="today-title">
    <div class="card-header">
      <h2 id="today-title">Today's habits</h2>
      <a href="/habits" class="small">Manage habits →</a>
    </div>

    {#if habits.initialLoading || todayActivities.initialLoading}
      <Loading label="Loading today's habits…" />
    {:else if habits.error}
      <ErrorState error={habits.error} retry={habits.refetch} />
    {:else if activeHabits.length === 0}
      <EmptyState icon="🌱" title="No habits yet" message="Create your first habit to start tracking.">
        <a class="btn btn-primary" href="/habits/new">Create a habit</a>
      </EmptyState>
    {:else}
      <div class="today-grid">
        <div class="ring">
          <tp-progress-ring value={doneCount} max={activeHabits.length} size={140} strokeWidth={12} tone="success" label="Habits completed today">
            <div class="ring-center">
              <strong>{doneCount}/{activeHabits.length}</strong>
              <span class="xsmall muted">done today</span>
            </div>
          </tp-progress-ring>
        </div>
        <ul class="list-plain habit-cards" aria-label="Habits for today">
          {#each activeHabits as habit (habit.id)}
            {@const done = doneIds.has(habit.id)}
            {@const streak = streakByHabit.get(habit.id)}
            <li>
              <tp-progress-card
                heading={habit.title}
                category={habit.category}
                value={done ? 1 : 0}
                target={1}
                unit="today"
                streak={streak?.current ?? 0}
                streakUnit={habit.frequency === 'weekly' ? 'week' : 'day'}
                completed={done}
                busy={!!busy[habit.id]}
                actionLabel="Mark complete"
                completedLabel="Done today"
                data-habit-id={habit.id}
                ontp-action={() => complete(habit)}
              >
                <span class="small muted">{habit.frequency === 'weekly' ? `${habit.target_per_period}× per week` : 'Daily'}{habit.visibility === 'team' ? ' · shared with team' : ''}</span>
                <a slot="actions" class="btn btn-ghost btn-sm" href="/habits/{habit.id}">Details</a>
              </tp-progress-card>
            </li>
          {/each}
        </ul>
      </div>
    {/if}
  </section>

  <!-- Trend -->
  <section class="card" aria-labelledby="trend-title">
    <div class="card-header">
      <h2 id="trend-title">Last 14 days</h2>
      <a href="/analytics" class="small">All insights →</a>
    </div>
    {#if insights.initialLoading}
      <Loading />
    {:else if insights.error}
      <ErrorState error={insights.error} retry={insights.refetch} />
    {:else}
      <tp-trend-chart series={trend} type="bar" height={220} label="Your completions per day, last 14 days" yLabel="Completions" showLegend={false}></tp-trend-chart>
    {/if}
  </section>

  <!-- Streak milestones -->
  <section class="card" aria-labelledby="streaks-title">
    <div class="card-header">
      <h2 id="streaks-title">Streak milestones</h2>
    </div>
    {#if streaks.initialLoading}
      <Loading />
    {:else if streaks.error}
      <ErrorState error={streaks.error} retry={streaks.refetch} />
    {:else if topStreaks.length === 0}
      <EmptyState icon="🔥" title="No active streaks" message="Complete a habit on consecutive days to start a streak." />
    {:else}
      <ul class="list-plain stack">
        {#each topStreaks as { streak, habit } (streak.habit_id)}
          {@const unit = streak.frequency === 'weekly' ? 'weeks' : 'days'}
          <li>
            <tp-progress-card
              heading={habit.title}
              category={habit.category}
              value={streak.current}
              target={nextMilestone(streak.current)}
              unit={unit}
              streak={streak.current}
              streakUnit={streak.frequency === 'weekly' ? 'week' : 'day'}
            >
              <span class="small muted">Longest: {streak.longest} {unit} · next milestone {nextMilestone(streak.current)} {unit}</span>
            </tp-progress-card>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  <!-- Challenges -->
  <section class="card" aria-labelledby="challenges-title">
    <div class="card-header">
      <h2 id="challenges-title">My active challenges</h2>
      <a href="/challenges?joined=true" class="small">All →</a>
    </div>
    {#if challenges.initialLoading}
      <Loading />
    {:else if challenges.error}
      <ErrorState error={challenges.error} retry={challenges.refetch} />
    {:else if (challenges.data?.items.length ?? 0) === 0}
      <EmptyState icon="🏆" title="No active challenges" message="Join a challenge to compete with your colleagues.">
        <a class="btn" href="/challenges?status=active">Find a challenge</a>
      </EmptyState>
    {:else}
      <ul class="list-plain challenge-list">
        {#each challenges.data?.items ?? [] as challenge (challenge.id)}
          <li>
            <a class="challenge card-link" href="/challenges/{challenge.id}">
              <tp-progress-ring value={challenge.my_score ?? 0} max={challenge.target_count} size={64} strokeWidth={7} tone={challenge.my_goal_reached ? 'success' : 'primary'} label="{challenge.title} progress"></tp-progress-ring>
              <span class="challenge-text">
                <strong>{challenge.title}</strong>
                <span class="xsmall muted">{challenge.my_score ?? 0} / {challenge.target_count} · ends {formatDate(challenge.ends_on)}</span>
              </span>
            </a>
          </li>
        {/each}
      </ul>
    {/if}
  </section>

  <!-- Badges -->
  <section class="card" aria-labelledby="badges-title">
    <div class="card-header">
      <h2 id="badges-title">Recent badges</h2>
      <a href="/analytics#badges" class="small">All badges →</a>
    </div>
    {#if badges.initialLoading}
      <Loading />
    {:else if badges.error}
      <ErrorState error={badges.error} retry={badges.refetch} />
    {:else if recentBadges.length === 0}
      <EmptyState icon="🎖️" title="No badges yet" message="Keep your streaks going to earn your first badge." />
    {:else}
      <div class="badge-grid">
        {#each recentBadges as badge (badge.code)}
          <tp-badge icon={badge.icon} name={badge.name} description={badge.description} awardedAt={badge.awarded_at}></tp-badge>
        {/each}
      </div>
    {/if}
  </section>

  {#if session.isManager}
    <!-- Manager: aggregated team snapshot -->
    <section class="card team" aria-labelledby="team-title">
      <div class="card-header">
        <h2 id="team-title">Team snapshot</h2>
        <a href="/team" class="small">Team insights →</a>
      </div>
      <p class="xsmall muted privacy">🛡️ Aggregated and anonymised — days with fewer than 3 active members are hidden.</p>
      {#if !snapshotTeamId}
        <EmptyState icon="👥" title="No managed team" message="You are not assigned as manager of a team yet." />
      {:else if teamSnapshot.initialLoading}
        <Loading />
      {:else if teamSnapshot.error}
        <ErrorState error={teamSnapshot.error} retry={teamSnapshot.refetch} />
      {:else if teamSnapshot.data}
        <div class="grid-tiles">
          <tp-stat-tile label="Team completions" value={String(teamSnapshot.data.totals.completions)} hint="last 14 days"></tp-stat-tile>
          <tp-stat-tile label="Avg active members" value={teamSnapshot.data.totals.avg_active_members.toFixed(1)}></tp-stat-tile>
        </div>
        <tp-trend-chart
          series={teamTrend.slice(0, 1)}
          height={160}
          label="Team completions per day (aggregated)"
          gapLabel={suppressedLabel(teamSnapshot.data.min_cohort_size)}
          showLegend={false}
        ></tp-trend-chart>
      {/if}
    </section>
  {/if}
</div>

<style>
  .layout {
    display: grid;
    gap: var(--tp-space-5);
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .today {
    grid-column: 1 / -1;
  }

  @media (max-width: 1000px) {
    .layout {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .today-grid {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: var(--tp-space-6);
    align-items: start;
  }

  @media (max-width: 720px) {
    .today-grid {
      grid-template-columns: minmax(0, 1fr);
      justify-items: center;
    }

    .today-grid .habit-cards {
      width: 100%;
    }
  }

  .ring-center {
    display: flex;
    flex-direction: column;
    align-items: center;
  }

  .ring-center strong {
    font-size: var(--tp-font-size-xl);
  }

  .habit-cards {
    display: grid;
    gap: var(--tp-space-3);
    grid-template-columns: repeat(auto-fill, minmax(min(100%, 15rem), 1fr));
  }

  .challenge-list {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-2);
  }

  .challenge {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
    padding: var(--tp-space-2) var(--tp-space-3);
    border: 1px solid var(--tp-glass-border);
    border-radius: var(--tp-radius-lg);
    background: var(--tp-glass-bg-strong);
    box-shadow: var(--tp-shadow-sm);
  }

  .challenge-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .badge-grid {
    display: grid;
    gap: var(--tp-space-3);
    grid-template-columns: repeat(auto-fill, minmax(8.5rem, 1fr));
  }

  .team {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-3);
  }

  .team .card-header {
    margin-bottom: 0;
  }
</style>
