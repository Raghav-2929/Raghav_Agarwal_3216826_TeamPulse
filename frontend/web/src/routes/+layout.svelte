<script lang="ts">
  // Central design tokens shipped by the component library — loaded once for the whole app.
  import '@teampulse/ui-components/tokens.css';
  import '../app.css';
  import { onMount, type Snippet } from 'svelte';
  import Toasts from '$lib/components/Toasts.svelte';
  import { theme } from '$lib/state/theme.svelte';

  let { children }: { children: Snippet } = $props();

  onMount(() => theme.init());
</script>

{@render children()}
<Toasts />
