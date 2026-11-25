<script lang="ts">
  import { page } from '$app/state';
  import ErrorPage from '$lib/components/ErrorPage.svelte';
</script>

<main class="standalone">
  <ErrorPage status={page.status} message={page.error?.message} />
</main>

<style>
  .standalone {
    min-height: 100vh;
    display: grid;
    place-items: center;
    padding: var(--tp-space-6);
  }
</style>
