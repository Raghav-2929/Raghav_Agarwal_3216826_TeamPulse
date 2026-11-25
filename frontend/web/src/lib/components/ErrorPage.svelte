<script lang="ts">
  interface Props {
    status: number;
    message?: string;
  }

  let { status, message }: Props = $props();

  const copy = $derived.by(() => {
    if (status === 403)
      return {
        icon: '🔒',
        title: 'Access denied',
        text: message || 'Your role does not have access to this page.',
      };
    if (status === 404) return { icon: '🧭', title: 'Page not found', text: message || 'We could not find what you were looking for.' };
    return { icon: '⚠️', title: 'Something went wrong', text: message || 'An unexpected error occurred.' };
  });
</script>

<section class="error-page card" aria-labelledby="error-title" data-status={status}>
  <span class="icon" aria-hidden="true">{copy.icon}</span>
  <p class="status">Error {status}</p>
  <h1 id="error-title">{copy.title}</h1>
  <p class="muted">{copy.text}</p>
  <div class="row">
    <a class="btn btn-primary" href="/dashboard">Go to dashboard</a>
    <button type="button" class="btn" onclick={() => history.back()}>Go back</button>
  </div>
</section>

<style>
  .error-page {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--tp-space-3);
    max-width: 32rem;
    margin: var(--tp-space-8) auto;
    text-align: center;
    padding: var(--tp-space-8);
  }

  .icon {
    font-size: 2.5rem;
  }

  .status {
    font-size: var(--tp-font-size-xs);
    font-weight: var(--tp-font-weight-semibold);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--tp-color-text-subtle);
  }
</style>
