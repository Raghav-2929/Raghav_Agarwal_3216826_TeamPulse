<script lang="ts">
  import Modal from './Modal.svelte';

  interface Props {
    open: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    danger?: boolean;
    busy?: boolean;
    onconfirm: () => void | Promise<void>;
  }

  let { open = $bindable(false), title, message, confirmLabel = 'Confirm', danger = false, busy = false, onconfirm }: Props = $props();
</script>

<Modal bind:open {title} size="sm">
  <p>{message}</p>
  {#snippet footer()}
    <button type="button" class="btn" onclick={() => (open = false)} disabled={busy}>Cancel</button>
    <button type="button" class="btn {danger ? 'btn-danger' : 'btn-primary'}" onclick={onconfirm} disabled={busy}>
      {busy ? 'Working…' : confirmLabel}
    </button>
  {/snippet}
</Modal>
