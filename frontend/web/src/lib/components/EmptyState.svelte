<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    icon?: string;
    title: string;
    message?: string;
    children?: Snippet;
  }

  let { icon = '🌱', title, message, children }: Props = $props();
</script>

<div class="empty" role="note">
  <span class="icon" aria-hidden="true">{icon}</span>
  <p class="title">{title}</p>
  {#if message}<p class="muted small">{message}</p>{/if}
  {#if children}<div class="actions">{@render children()}</div>{/if}
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--tp-space-2);
    padding: var(--tp-space-8) var(--tp-space-4);
    text-align: center;
    border: 1px dashed color-mix(in srgb, var(--tp-color-border-strong) 80%, transparent);
    border-radius: var(--tp-radius-lg);
    background: var(--tp-glass-bg-subtle);
  }

  .icon {
    display: grid;
    place-items: center;
    width: 3.5rem;
    height: 3.5rem;
    margin-bottom: var(--tp-space-1);
    border-radius: 50%;
    background: var(--tp-glass-bg-strong);
    box-shadow: var(--tp-shadow-sm);
    font-size: 1.6rem;
  }

  .title {
    font-weight: var(--tp-font-weight-semibold);
  }

  .actions {
    margin-top: var(--tp-space-2);
  }
</style>
