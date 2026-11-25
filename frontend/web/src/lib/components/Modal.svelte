<script lang="ts">
  import type { Snippet } from 'svelte';

  interface Props {
    open: boolean;
    title: string;
    description?: string;
    size?: 'sm' | 'md' | 'lg';
    children?: Snippet;
    footer?: Snippet;
    onclose?: () => void;
  }

  let { open = $bindable(false), title, description, size = 'md', children, footer, onclose }: Props = $props();

  let dialog = $state<HTMLDialogElement>();
  const id = `modal-${Math.random().toString(36).slice(2, 9)}`;

  // Native <dialog>: focus trapping, Escape to close and inert background come for free.
  $effect(() => {
    if (!dialog) return;
    if (open && !dialog.open) {
      if (typeof dialog.showModal === 'function') dialog.showModal();
      else dialog.setAttribute('open', '');
    } else if (!open && dialog.open) {
      dialog.close();
    }
  });

  function handleClose() {
    if (open) open = false;
    onclose?.();
  }
</script>

<dialog
  bind:this={dialog}
  class="modal modal-{size}"
  aria-labelledby="{id}-title"
  aria-describedby={description ? `${id}-desc` : undefined}
  onclose={handleClose}
>
  {#if open}
    <div class="panel">
      <header class="head">
        <div>
          <h2 id="{id}-title">{title}</h2>
          {#if description}<p id="{id}-desc" class="muted small">{description}</p>{/if}
        </div>
        <button type="button" class="btn btn-ghost btn-icon" aria-label="Close dialog" onclick={() => (open = false)}>✕</button>
      </header>
      <div class="content">
        {@render children?.()}
      </div>
      {#if footer}
        <footer class="foot">{@render footer()}</footer>
      {/if}
    </div>
  {/if}
</dialog>

<style>
  .modal {
    padding: 0;
    border: 1px solid var(--tp-glass-border);
    border-radius: var(--tp-radius-xl);
    background: var(--tp-glass-bg-strong);
    -webkit-backdrop-filter: var(--tp-glass-blur);
    backdrop-filter: var(--tp-glass-blur);
    color: var(--tp-color-text);
    box-shadow: var(--tp-shadow-lg);
    width: min(32rem, calc(100vw - 2rem));
    max-height: calc(100vh - 2rem);
  }

  .modal-sm {
    width: min(26rem, calc(100vw - 2rem));
  }

  .modal-lg {
    width: min(44rem, calc(100vw - 2rem));
  }

  .modal::backdrop {
    background: var(--tp-color-overlay);
    -webkit-backdrop-filter: blur(6px);
    backdrop-filter: blur(6px);
  }

  .panel {
    display: flex;
    flex-direction: column;
    max-height: calc(100vh - 2rem);
  }

  .head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--tp-space-3);
    padding: var(--tp-space-5) var(--tp-space-5) var(--tp-space-3);
  }

  .head h2 {
    font-size: var(--tp-font-size-lg);
  }

  .content {
    padding: 0 var(--tp-space-5) var(--tp-space-5);
    overflow-y: auto;
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    gap: var(--tp-space-3);
    padding: var(--tp-space-4) var(--tp-space-5);
    border-top: 1px solid color-mix(in srgb, var(--tp-color-border) 70%, transparent);
  }
</style>
