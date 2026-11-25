<script lang="ts">
  import type { ChallengeStatus } from '$lib/api/types';

  let { status }: { status: ChallengeStatus } = $props();

  const tone = $derived(status === 'active' ? 'pill-success' : status === 'upcoming' ? 'pill-info' : '');
  const label = $derived(status.charAt(0).toUpperCase() + status.slice(1));
</script>

<span class="pill {tone}">{label}</span>
