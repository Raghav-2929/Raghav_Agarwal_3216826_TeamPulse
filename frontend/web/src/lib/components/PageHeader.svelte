<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    title: string;
    description?: string;
    back?: { href: string; label: string };
    actions?: Snippet;
  }

  let { title, description, back, actions }: Props = $props();
</script>

<header class="page-header">
  {#if back}
    <a class="back" href={back.href}><span aria-hidden="true">←</span> {back.label}</a>
  {/if}
  <div class="row-between">
    <div class="titles">
      <h1>{title}</h1>
      {#if description}<p class="muted">{description}</p>{/if}
    </div>
    {#if actions}
      <div class="row">{@render actions()}</div>
    {/if}
  </div>
</header>

<style>
  .page-header {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-2);
  }

  .titles {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-1);
    min-width: 0;
  }

  h1 {
    overflow-wrap: anywhere;
  }

  .back {
    font-size: var(--tp-font-size-sm);
    text-decoration: none;
    width: fit-content;
  }
</style>
