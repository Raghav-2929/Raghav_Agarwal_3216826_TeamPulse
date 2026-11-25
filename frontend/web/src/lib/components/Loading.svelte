<script lang="ts">
  interface Props {
    label?: string;
    inline?: boolean;
  }

  let { label = 'Loading…', inline = false }: Props = $props();
</script>

<div class="loading" class:inline role="status" aria-live="polite">
  <span class="spinner" aria-hidden="true"></span>
  <span>{label}</span>
</div>

<style>
  .loading {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--tp-space-3);
    padding: var(--tp-space-8) var(--tp-space-4);
    color: var(--tp-color-text-muted);
    font-size: var(--tp-font-size-sm);
  }

  .loading.inline {
    display: inline-flex;
    padding: 0;
  }

  .spinner {
    width: 1.1rem;
    height: 1.1rem;
    border-radius: 50%;
    border: 2px solid var(--tp-color-border-strong);
    border-top-color: var(--tp-color-primary);
    animation: spin 0.8s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation-duration: 2.4s;
    }
  }
</style>
