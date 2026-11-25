<script lang="ts">
  import type { Snippet } from 'svelte';
  import { page } from '$app/state';

  let { children }: { children: Snippet } = $props();

  const tabs = [
    { href: '/admin/users', label: 'Users' },
    { href: '/admin/teams', label: 'Teams' },
    { href: '/admin/badge-rules', label: 'Badge rules' },
    { href: '/admin/insights', label: 'Org insights' },
  ];
</script>

<nav class="admin-tabs" aria-label="Administration sections">
  {#each tabs as tab (tab.href)}
    <a href={tab.href} aria-current={page.url.pathname.startsWith(tab.href) ? 'page' : undefined}>{tab.label}</a>
  {/each}
</nav>

{@render children()}

<style>
  .admin-tabs {
    display: flex;
    gap: var(--tp-space-1);
    width: fit-content;
    max-width: 100%;
    padding: 5px;
    overflow-x: auto;
    border-radius: var(--tp-radius-pill);
    background: var(--tp-glass-bg);
    -webkit-backdrop-filter: var(--tp-glass-blur);
    backdrop-filter: var(--tp-glass-blur);
    border: 1px solid var(--tp-glass-border);
    box-shadow: var(--tp-glass-shadow);
  }

  .admin-tabs a {
    padding: var(--tp-space-2) var(--tp-space-5);
    border-radius: var(--tp-radius-pill);
    color: var(--tp-color-text-muted);
    font-size: var(--tp-font-size-sm);
    font-weight: var(--tp-font-weight-medium);
    text-decoration: none;
    white-space: nowrap;
    transition:
      background var(--tp-duration-fast) var(--tp-easing-standard),
      color var(--tp-duration-fast) var(--tp-easing-standard);
  }

  .admin-tabs a:hover {
    color: var(--tp-color-text);
    background: var(--tp-color-surface-hover);
  }

  .admin-tabs a[aria-current='page'] {
    background: var(--tp-gradient-primary);
    color: var(--tp-color-primary-contrast);
    font-weight: var(--tp-font-weight-semibold);
    box-shadow: var(--tp-shadow-primary);
  }
</style>
