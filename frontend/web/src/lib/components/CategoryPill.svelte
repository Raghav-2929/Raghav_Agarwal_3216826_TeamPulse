<script lang="ts">
  import { categoryColor, categoryIcon, categoryLabel } from '$lib/utils/categories';

  interface Props {
    category: string | null | undefined;
    fallback?: string;
  }

  let { category, fallback = 'Any activity' }: Props = $props();
</script>

<span class="pill cat" style:--cat={categoryColor(category)}>
  <span aria-hidden="true">{categoryIcon(category)}</span>
  {category ? categoryLabel(category) : fallback}
</span>

<style>
  .cat {
    background: color-mix(in srgb, var(--cat) 14%, transparent);
    color: var(--tp-color-text);
  }
</style>
