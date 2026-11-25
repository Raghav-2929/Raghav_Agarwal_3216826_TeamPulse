<script lang="ts">
  import { page } from '$app/state';
  import Icon, { NAV_ICONS } from '$lib/components/Icon.svelte';
  import { notifications } from '$lib/state/notifications.svelte';
  import { session } from '$lib/state/session.svelte';
  import { activeHref, navForRole } from '$lib/utils/nav';

  let { open = $bindable(false) }: { open?: boolean } = $props();

  // Role → routes config drives the menu; links a role may not open are never rendered.
  const sections = $derived(navForRole(session.role));
  const active = $derived(activeHref(page.url.pathname));
</script>

<nav id="app-sidebar" class="sidebar" class:open aria-label="Main navigation">
  <a class="brand" href="/dashboard" onclick={() => (open = false)}>
    <span class="logo" aria-hidden="true">
      <svg viewBox="0 0 32 32" width="22" height="22">
        <path d="M4 17h6l3-7 4 13 3-6h8" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </span>
    <span class="brand-text">
      <span class="brand-name">TeamPulse</span>
      <span class="brand-tag">Team wellness</span>
    </span>
  </a>

  <div class="sections">
    {#each sections as section (section.id)}
      <div class="section">
        <p class="section-label" id="nav-section-{section.id}">{section.label}</p>
        <ul aria-labelledby="nav-section-{section.id}">
          {#each section.items as item (item.href)}
            <li>
              <a href={item.href} aria-current={active === item.href ? 'page' : undefined} onclick={() => (open = false)}>
                <span class="icon" aria-hidden="true">
                  {#if NAV_ICONS[item.href]}
                    <Icon name={NAV_ICONS[item.href]} size={18} />
                  {:else}
                    {item.icon}
                  {/if}
                </span>
                <span class="label">{item.label}</span>
                {#if item.href === '/notifications' && notifications.unread > 0}
                  <span class="count" aria-label="{notifications.unread} unread">{notifications.unread > 99 ? '99+' : notifications.unread}</span>
                {/if}
              </a>
            </li>
          {/each}
        </ul>
      </div>
    {/each}
  </div>

  <div class="privacy">
    <span class="privacy-icon" aria-hidden="true"><Icon name="shield" size={18} /></span>
    <p>
      <strong>Private by design</strong>
      <span>Managers see team totals only, never your personal data.</span>
    </p>
  </div>
</nav>

{#if open}
  <button type="button" class="scrim" aria-label="Close navigation" onclick={() => (open = false)}></button>
{/if}

<style>
  .sidebar {
    position: sticky;
    top: var(--tp-shell-gap);
    flex: none;
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-5);
    width: var(--tp-sidebar-width);
    height: calc(100vh - 2 * var(--tp-shell-gap));
    margin: var(--tp-shell-gap) 0 var(--tp-shell-gap) var(--tp-shell-gap);
    padding: var(--tp-space-5) var(--tp-space-3) var(--tp-space-3);
    overflow-y: auto;
    background: var(--tp-glass-bg);
    -webkit-backdrop-filter: var(--tp-glass-blur);
    backdrop-filter: var(--tp-glass-blur);
    border: 1px solid var(--tp-glass-border);
    border-radius: var(--tp-radius-xl);
    box-shadow: var(--tp-glass-shadow);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
    padding: 0 var(--tp-space-2);
    color: var(--tp-color-text);
    text-decoration: none;
  }

  .brand:hover {
    color: var(--tp-color-text);
  }

  .logo {
    display: grid;
    place-items: center;
    width: 2.5rem;
    height: 2.5rem;
    border-radius: var(--tp-radius-md);
    background: var(--tp-gradient-primary);
    color: var(--tp-color-primary-contrast);
    box-shadow: var(--tp-shadow-primary);
  }

  .brand-text {
    display: flex;
    flex-direction: column;
    line-height: 1.15;
  }

  .brand-name {
    font-size: var(--tp-font-size-lg);
    font-weight: var(--tp-font-weight-bold);
    letter-spacing: -0.02em;
  }

  .brand-tag {
    font-size: var(--tp-font-size-xs);
    color: var(--tp-color-text-subtle);
  }

  .sections {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-3);
  }

  .section-label {
    padding: 0 var(--tp-space-3);
    margin-bottom: var(--tp-space-2);
    font-size: 0.6875rem;
    font-weight: var(--tp-font-weight-semibold);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--tp-color-text-subtle);
  }

  ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .section a {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
    padding: 0.3rem var(--tp-space-3) 0.3rem 0.3rem;
    border-radius: var(--tp-radius-md);
    color: var(--tp-color-text-muted);
    font-size: var(--tp-font-size-sm);
    font-weight: var(--tp-font-weight-medium);
    text-decoration: none;
    transition:
      background var(--tp-duration-fast) var(--tp-easing-standard),
      color var(--tp-duration-fast) var(--tp-easing-standard);
  }

  .section a:hover {
    background: var(--tp-color-surface-hover);
    color: var(--tp-color-text);
  }

  .icon {
    display: grid;
    place-items: center;
    width: 2rem;
    height: 2rem;
    border-radius: 10px;
    background: var(--tp-glass-bg-subtle);
    border: 1px solid var(--tp-glass-border);
    color: var(--tp-color-text-muted);
    font-size: 0.95rem;
    transition:
      background var(--tp-duration-fast) var(--tp-easing-standard),
      color var(--tp-duration-fast) var(--tp-easing-standard);
  }

  .section a:hover .icon {
    color: var(--tp-color-primary);
  }

  .section a[aria-current='page'] {
    background: var(--tp-gradient-primary);
    color: var(--tp-color-primary-contrast);
    font-weight: var(--tp-font-weight-semibold);
    box-shadow: var(--tp-shadow-primary);
  }

  .section a[aria-current='page'] .icon {
    background: rgb(255 255 255 / 0.18);
    border-color: rgb(255 255 255 / 0.25);
    color: var(--tp-color-primary-contrast);
  }

  .label {
    flex: 1;
  }

  .count {
    min-width: 1.4rem;
    padding: 1px var(--tp-space-2);
    border-radius: var(--tp-radius-pill);
    background: var(--tp-color-danger);
    color: var(--tp-color-text-inverse);
    font-size: var(--tp-font-size-xs);
    font-weight: var(--tp-font-weight-bold);
    text-align: center;
  }

  .privacy {
    display: flex;
    gap: var(--tp-space-3);
    align-items: flex-start;
    padding: var(--tp-space-3);
    border-radius: var(--tp-radius-lg);
    background: linear-gradient(140deg, color-mix(in srgb, var(--tp-color-primary) 12%, transparent), color-mix(in srgb, var(--tp-color-category-mindfulness) 10%, transparent));
    border: 1px solid var(--tp-glass-border);
    font-size: var(--tp-font-size-xs);
    color: var(--tp-color-text-muted);
  }

  .privacy p {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .privacy strong {
    color: var(--tp-color-text);
    font-size: var(--tp-font-size-xs);
  }

  /* Admins have the longest menu (and manage the data), so the note makes room for it. */
  .sidebar:has(#nav-section-admin) .privacy {
    display: none;
  }

  .privacy-icon {
    display: grid;
    place-items: center;
    flex: none;
    width: 2rem;
    height: 2rem;
    border-radius: 10px;
    background: var(--tp-glass-bg-strong);
    color: var(--tp-color-primary);
  }

  .scrim {
    display: none;
  }

  @media (max-width: 900px) {
    .sidebar {
      position: fixed;
      inset: var(--tp-shell-gap) auto var(--tp-shell-gap) var(--tp-shell-gap);
      z-index: var(--tp-z-overlay);
      height: auto;
      margin: 0;
      background: var(--tp-glass-bg-strong);
      transform: translateX(calc(-100% - 2 * var(--tp-shell-gap)));
      transition: transform var(--tp-duration-normal) var(--tp-easing-standard);
      box-shadow: var(--tp-shadow-lg);
    }

    .sidebar.open {
      transform: none;
    }

    .scrim {
      display: block;
      position: fixed;
      inset: 0;
      z-index: calc(var(--tp-z-overlay) - 1);
      border: 0;
      background: var(--tp-color-overlay);
      -webkit-backdrop-filter: blur(4px);
      backdrop-filter: blur(4px);
      cursor: pointer;
    }
  }
</style>
