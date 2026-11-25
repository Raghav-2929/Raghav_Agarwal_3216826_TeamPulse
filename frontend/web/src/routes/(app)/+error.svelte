<script lang="ts">
  import { page } from '$app/state';
  import ErrorPage from '$lib/components/ErrorPage.svelte';
</script>

<svelte:head>
  <title>{page.status === 403 ? 'Access denied' : 'Error'} · TeamPulse</title>
</svelte:head>

<ErrorPage status={page.status} message={page.error?.message} />
