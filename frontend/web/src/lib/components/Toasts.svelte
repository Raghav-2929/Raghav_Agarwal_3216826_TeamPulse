<script lang="ts">
  import { toasts } from '$lib/state/toasts.svelte';

  const icons = { success: '✅', error: '⚠️', info: 'ℹ️' } as const;
</script>

<div class="toasts" aria-live="polite" aria-relevant="additions">
  {#each toasts.items as toast (toast.id)}
    <div class="toast toast-{toast.kind}" role={toast.kind === 'error' ? 'alert' : 'status'}>
      <span aria-hidden="true">{icons[toast.kind]}</span>
      <p>{toast.message}</p>
      <button type="button" class="dismiss" aria-label="Dismiss notification" onclick={() => toasts.dismiss(toast.id)}>✕</button>
    </div>
  {/each}
</div>

<style>
  .toasts {
    position: fixed;
    right: var(--tp-space-4);
    bottom: var(--tp-space-4);
    z-index: var(--tp-z-toast);
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-2);
    width: min(24rem, calc(100vw - 2rem));
    pointer-events: none;
  }

  .toast {
    pointer-events: auto;
    display: flex;
    align-items: flex-start;
    gap: var(--tp-space-3);
    padding: var(--tp-space-3) var(--tp-space-4);
    border-radius: var(--tp-radius-lg);
    background: var(--tp-glass-bg-strong);
    -webkit-backdrop-filter: var(--tp-glass-blur);
    backdrop-filter: var(--tp-glass-blur);
    border: 1px solid var(--tp-glass-border);
    box-shadow:
      inset 4px 0 0 var(--toast-accent, var(--tp-color-info)),
      var(--tp-shadow-lg);
    font-size: var(--tp-font-size-sm);
    animation: toast-in var(--tp-duration-normal) var(--tp-easing-standard);
  }

  .toast p {
    flex: 1;
  }

  .toast-success {
    --toast-accent: var(--tp-color-success);
  }

  .toast-error {
    --toast-accent: var(--tp-color-danger);
  }

  .dismiss {
    border: 0;
    background: transparent;
    color: var(--tp-color-text-muted);
    cursor: pointer;
    padding: 0 var(--tp-space-1);
  }

  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateY(8px);
    }
  }
</style>
