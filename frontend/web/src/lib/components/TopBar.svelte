<script lang="ts">
  import { goto } from '$app/navigation';
  import Icon, { type IconName } from '$lib/components/Icon.svelte';
  import { notifications } from '$lib/state/notifications.svelte';
  import { session } from '$lib/state/session.svelte';
  import { theme } from '$lib/state/theme.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { ROLE_LABELS } from '$lib/utils/nav';

  let { sidebarOpen = $bindable(false) }: { sidebarOpen?: boolean } = $props();

  let menuOpen = $state(false);
  let signingOut = $state(false);

  const initials = $derived(
    (session.user?.full_name ?? '?')
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join(''),
  );
  const unreadLabel = $derived(notifications.unread > 99 ? '99+' : String(notifications.unread));
  const themeLabel = $derived(theme.preference === 'system' ? 'System theme' : theme.preference === 'light' ? 'Light theme' : 'Dark theme');
  const themeIcon = $derived<IconName>(theme.preference === 'system' ? 'monitor' : theme.preference === 'light' ? 'sun' : 'moon');
  const todayLabel = new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

  async function signOut() {
    signingOut = true;
    menuOpen = false;
    await session.logout();
    notifications.stop();
    notifications.reset();
    toasts.info('You have been signed out.');
    await goto('/login', { replaceState: true });
    signingOut = false;
  }

  function onWindowKeydown(event: KeyboardEvent) {
    if (event.key === 'Escape' && menuOpen) menuOpen = false;
  }
</script>

<svelte:window onkeydown={onWindowKeydown} />

<div class="topbar-wrap">
  <header class="topbar">
    <button
      type="button"
      class="tool menu-toggle"
      aria-controls="app-sidebar"
      aria-expanded={sidebarOpen}
      aria-label={sidebarOpen ? 'Close navigation' : 'Open navigation'}
      onclick={() => (sidebarOpen = !sidebarOpen)}><Icon name="menu" /></button
    >

    <p class="today">
      <span class="today-icon" aria-hidden="true"><Icon name="calendar" size={16} /></span>
      <span>{todayLabel}</span>
    </p>

    <div class="spacer"></div>

    <button type="button" class="tool" title={themeLabel} aria-label="{themeLabel} (change theme)" onclick={() => theme.cycle()}>
      <Icon name={themeIcon} />
    </button>

    <a class="tool bell" href="/notifications" aria-label="Notifications, {notifications.unread} unread">
      <Icon name="bell" />
      {#if notifications.unread > 0}
        <span class="badge" aria-hidden="true">{unreadLabel}</span>
      {/if}
    </a>

    <span class="separator" aria-hidden="true"></span>

    <details class="user-menu" bind:open={menuOpen}>
      <summary aria-label="Account menu for {session.user?.full_name ?? 'user'}">
        <span class="avatar" aria-hidden="true">{initials}</span>
        <span class="who">
          <span class="name">{session.user?.full_name}</span>
          <span class="role">{session.role ? ROLE_LABELS[session.role] : ''}{session.user?.team_name ? ` · ${session.user.team_name}` : ''}</span>
        </span>
        <span aria-hidden="true" class="caret"><Icon name="chevron-down" size={16} /></span>
      </summary>
      <div class="menu">
        <div class="menu-head">
          <span class="avatar avatar-lg" aria-hidden="true">{initials}</span>
          <div>
            <p class="small"><strong>{session.user?.full_name}</strong></p>
            <p class="xsmall muted">{session.user?.email}</p>
          </div>
        </div>
        <hr class="divider" />
        <a href="/profile" onclick={() => (menuOpen = false)}><Icon name="user" size={18} /> Profile</a>
        <a href="/notifications" onclick={() => (menuOpen = false)}><Icon name="bell" size={18} /> Notifications</a>
        <button type="button" class="signout" onclick={signOut} disabled={signingOut}><Icon name="logout" size={18} /> {signingOut ? 'Signing out…' : 'Sign out'}</button>
      </div>
    </details>
  </header>
</div>

<style>
  /* Sticky strip: the bar floats below a soft frosted fade, so content never shows sharply above it. */
  .topbar-wrap {
    position: sticky;
    top: 0;
    z-index: var(--tp-z-sticky);
    padding-top: var(--tp-shell-gap);
  }

  .topbar-wrap::before {
    content: '';
    position: absolute;
    inset: 0 calc(-1 * var(--tp-shell-gap)) -14px;
    z-index: -1;
    -webkit-backdrop-filter: blur(10px);
    backdrop-filter: blur(10px);
    -webkit-mask-image: linear-gradient(to bottom, #000 60%, transparent);
    mask-image: linear-gradient(to bottom, #000 60%, transparent);
    pointer-events: none;
  }

  .topbar {
    position: relative;
    display: flex;
    align-items: center;
    gap: var(--tp-space-2);
    width: 100%;
    max-width: var(--tp-content-max-width);
    min-height: var(--tp-header-height);
    margin: 0 auto;
    padding: var(--tp-space-2) var(--tp-space-3) var(--tp-space-2) var(--tp-space-5);
    background: var(--tp-glass-bg);
    -webkit-backdrop-filter: var(--tp-glass-blur);
    backdrop-filter: var(--tp-glass-blur);
    border: 1px solid var(--tp-glass-border);
    border-radius: var(--tp-radius-xl);
    box-shadow: var(--tp-glass-shadow);
  }

  .spacer {
    flex: 1;
  }

  .today {
    display: flex;
    align-items: center;
    gap: var(--tp-space-2);
    font-size: var(--tp-font-size-sm);
    font-weight: var(--tp-font-weight-medium);
    color: var(--tp-color-text-muted);
    white-space: nowrap;
  }

  .today-icon {
    display: grid;
    place-items: center;
    width: 2rem;
    height: 2rem;
    border-radius: 10px;
    background: var(--tp-color-primary-soft);
    color: var(--tp-color-primary);
  }

  .tool {
    position: relative;
    display: inline-grid;
    place-items: center;
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 50%;
    border: 1px solid var(--tp-glass-border);
    background: var(--tp-glass-bg-strong);
    color: var(--tp-color-text-muted);
    box-shadow: var(--tp-shadow-sm);
    cursor: pointer;
    transition:
      color var(--tp-duration-fast) var(--tp-easing-standard),
      box-shadow var(--tp-duration-fast) var(--tp-easing-standard);
  }

  .tool:hover {
    color: var(--tp-color-primary);
    box-shadow: var(--tp-shadow-md);
  }

  .menu-toggle {
    display: none;
  }

  @media (max-width: 900px) {
    .menu-toggle {
      display: inline-grid;
    }

    .topbar {
      padding-left: var(--tp-space-3);
    }
  }

  @media (max-width: 640px) {
    .today {
      display: none;
    }
  }

  .badge {
    position: absolute;
    top: -3px;
    right: -3px;
    min-width: 1.15rem;
    padding: 0 4px;
    border-radius: var(--tp-radius-pill);
    background: var(--tp-color-danger);
    color: var(--tp-color-text-inverse);
    box-shadow: 0 0 0 2px var(--tp-color-surface);
    font-size: 0.65rem;
    font-weight: var(--tp-font-weight-bold);
    line-height: 1.15rem;
    text-align: center;
  }

  .separator {
    width: 1px;
    height: 1.75rem;
    margin: 0 var(--tp-space-2);
    background: var(--tp-color-border);
  }

  .user-menu {
    position: relative;
  }

  summary {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
    padding: var(--tp-space-1) var(--tp-space-2) var(--tp-space-1) var(--tp-space-1);
    border-radius: var(--tp-radius-pill);
    cursor: pointer;
    list-style: none;
    transition: background var(--tp-duration-fast) var(--tp-easing-standard);
  }

  summary::-webkit-details-marker {
    display: none;
  }

  summary:hover {
    background: var(--tp-color-surface-hover);
  }

  .avatar {
    display: grid;
    place-items: center;
    flex: none;
    width: 2.4rem;
    height: 2.4rem;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--tp-color-category-mindfulness), var(--tp-color-primary));
    color: var(--tp-color-primary-contrast);
    box-shadow: 0 0 0 2px var(--tp-glass-border), var(--tp-shadow-sm);
    font-size: var(--tp-font-size-sm);
    font-weight: var(--tp-font-weight-bold);
  }

  .avatar-lg {
    width: 2.75rem;
    height: 2.75rem;
  }

  .who {
    display: flex;
    flex-direction: column;
    line-height: 1.25;
  }

  .name {
    font-size: var(--tp-font-size-sm);
    font-weight: var(--tp-font-weight-semibold);
  }

  .role {
    font-size: var(--tp-font-size-xs);
    color: var(--tp-color-text-subtle);
  }

  .caret {
    color: var(--tp-color-text-subtle);
  }

  @media (max-width: 560px) {
    .who,
    .caret {
      display: none;
    }
  }

  .menu {
    position: absolute;
    right: 0;
    top: calc(100% + var(--tp-space-3));
    min-width: 16rem;
    padding: var(--tp-space-3);
    background: var(--tp-glass-bg-strong);
    -webkit-backdrop-filter: var(--tp-glass-blur);
    backdrop-filter: var(--tp-glass-blur);
    border: 1px solid var(--tp-glass-border);
    border-radius: var(--tp-radius-lg);
    box-shadow: var(--tp-shadow-lg);
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .menu-head {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
    padding: var(--tp-space-1);
  }

  .menu .divider {
    margin: var(--tp-space-2) 0;
  }

  .menu a,
  .signout {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
    width: 100%;
    padding: var(--tp-space-2) var(--tp-space-3);
    border: 0;
    border-radius: var(--tp-radius-md);
    background: transparent;
    color: var(--tp-color-text);
    font: inherit;
    font-size: var(--tp-font-size-sm);
    text-align: left;
    text-decoration: none;
    cursor: pointer;
  }

  .menu a:hover,
  .signout:hover {
    background: var(--tp-color-primary-soft);
    color: var(--tp-color-primary);
  }

  .signout {
    color: var(--tp-color-danger);
  }

  .signout:hover {
    background: var(--tp-color-danger-soft);
    color: var(--tp-color-danger);
  }
</style>
