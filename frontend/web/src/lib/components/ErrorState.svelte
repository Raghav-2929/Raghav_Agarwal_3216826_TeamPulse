<script lang="ts">
  import { errorMessage, isApiError } from '$lib/api/errors';

  interface Props {
    error: unknown;
    title?: string;
    retry?: () => void;
  }

  let { error, title = 'Could not load this section', retry }: Props = $props();
  const requestId = $derived(isApiError(error) ? error.requestId : undefined);
</script>

<div class="error" role="alert">
  <span class="icon" aria-hidden="true">⚠️</span>
  <div class="body">
    <p class="title">{title}</p>
    <p class="small">{errorMessage(error)}</p>
    {#if requestId}<p class="xsmall subtle">Reference: <code>{requestId}</code></p>{/if}
  </div>
  {#if retry}
    <button type="button" class="btn btn-sm" onclick={retry}>Try again</button>
  {/if}
</div>

<style>
  .error {
    display: flex;
    align-items: flex-start;
    gap: var(--tp-space-3);
    padding: var(--tp-space-4);
    border-radius: var(--tp-radius-lg);
    background: var(--tp-color-danger-soft);
    border: 1px solid color-mix(in srgb, var(--tp-color-danger) 30%, transparent);
    color: var(--tp-color-text);
  }

  .body {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-1);
  }

  .title {
    font-weight: var(--tp-font-weight-semibold);
    color: var(--tp-color-danger);
  }
</style>
