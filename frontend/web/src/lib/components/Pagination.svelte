<script lang="ts">
  interface Props {
    page: number;
    size: number;
    total: number;
    onchange: (page: number) => void;
    label?: string;
  }

  let { page, size, total, onchange, label = 'Pagination' }: Props = $props();

  const pages = $derived(Math.max(1, Math.ceil(total / Math.max(1, size))));
  const first = $derived(total === 0 ? 0 : (page - 1) * size + 1);
  const last = $derived(Math.min(total, page * size));
</script>

{#if total > 0}
  <nav class="pagination" aria-label={label}>
    <p class="small muted" aria-live="polite">Showing <strong>{first}–{last}</strong> of <strong>{total}</strong></p>
    {#if pages > 1}
      <div class="row">
        <button type="button" class="btn btn-sm" disabled={page <= 1} onclick={() => onchange(page - 1)}>
          <span aria-hidden="true">←</span> Previous
        </button>
        <span class="small">Page {page} of {pages}</span>
        <button type="button" class="btn btn-sm" disabled={page >= pages} onclick={() => onchange(page + 1)}>
          Next <span aria-hidden="true">→</span>
        </button>
      </div>
    {/if}
  </nav>
{/if}

<style>
  .pagination {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--tp-space-3);
    flex-wrap: wrap;
  }
</style>
