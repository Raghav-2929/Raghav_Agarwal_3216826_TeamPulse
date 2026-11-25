<script lang="ts">
  import Icon from './Icon.svelte';

  interface Props {
    value: string;
    label?: string;
    placeholder?: string;
    id?: string;
    oninput?: () => void;
  }

  let { value = $bindable(''), label = 'Search', placeholder = 'Search…', id = 'search', oninput }: Props = $props();

  function clear() {
    value = '';
    oninput?.();
  }
</script>

<div class="field grow">
  <label for={id}>{label}</label>
  <div class="search">
    <span class="icon" aria-hidden="true"><Icon name="search" size={17} /></span>
    <input {id} class="input" type="search" {placeholder} bind:value maxlength="100" autocomplete="off" {oninput} />
    {#if value}
      <button type="button" class="clear" aria-label="Clear search" onclick={clear}><Icon name="close" size={16} /></button>
    {/if}
  </div>
</div>

<style>
  .search {
    position: relative;
  }

  .icon {
    position: absolute;
    left: var(--tp-space-4);
    top: 50%;
    transform: translateY(-50%);
    color: var(--tp-color-text-subtle);
    pointer-events: none;
  }

  .search :global(.input) {
    padding-left: 2.6rem;
    padding-right: 2.6rem;
  }

  .search :global(.input::-webkit-search-cancel-button) {
    display: none;
  }

  .clear {
    position: absolute;
    right: var(--tp-space-2);
    top: 50%;
    transform: translateY(-50%);
    display: grid;
    place-items: center;
    border: 0;
    background: transparent;
    color: var(--tp-color-text-muted);
    cursor: pointer;
    padding: var(--tp-space-1);
    border-radius: 50%;
  }

  .clear:hover {
    background: var(--tp-color-surface-muted);
  }
</style>
