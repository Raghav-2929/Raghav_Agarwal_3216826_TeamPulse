<script lang="ts">
  import type { Snippet } from 'svelte';
  import { afterNavigate } from '$app/navigation';
  import Sidebar from '$lib/components/Sidebar.svelte';
  import TopBar from '$lib/components/TopBar.svelte';
  import { notifications } from '$lib/state/notifications.svelte';

  let { children }: { children: Snippet } = $props();
  let sidebarOpen = $state(false);

  // Poll the unread-notification count every 60 s while the shell is mounted.
  $effect(() => notifications.start());

  afterNavigate(() => {
    sidebarOpen = false;
  });
</script>

<a class="skip-link" href="#main-content">Skip to main content</a>

<div class="shell">
  <Sidebar bind:open={sidebarOpen} />
  <div class="main-col">
    <TopBar bind:sidebarOpen />
    <main id="main-content" tabindex="-1">
      <div class="content page-enter">
        {@render children()}
      </div>
    </main>
  </div>
</div>

<style>
  .shell {
    display: flex;
    align-items: flex-start;
    min-height: 100vh;
  }

  .main-col {
    flex: 1;
    min-width: 0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    padding: 0 var(--tp-shell-gap);
  }

  main {
    flex: 1;
    outline: none;
  }

  .content {
    width: 100%;
    max-width: var(--tp-content-max-width);
    margin: 0 auto;
    padding: var(--tp-space-8) 0 var(--tp-space-12);
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-6);
  }

  @media (max-width: 640px) {
    .main-col {
      padding: 0 var(--tp-space-3);
    }

    .content {
      padding: var(--tp-space-5) 0 var(--tp-space-10);
      gap: var(--tp-space-5);
    }
  }
</style>
