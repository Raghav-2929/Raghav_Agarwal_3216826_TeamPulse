<script lang="ts">
  import { RANGE_PRESETS, detectPreset, presetRange, todayISO, validateRange, type RangePreset, type RangePresetId } from '$lib/utils/dates';

  interface Props {
    from: string;
    to: string;
    maxDays?: number;
    idPrefix?: string;
    label?: string;
    onchange?: () => void;
  }

  let { from = $bindable(), to = $bindable(), maxDays = 180, idPrefix = 'range', label = 'Date range', onchange }: Props = $props();

  const today = todayISO();
  let forceCustom = $state(false);
  const selected = $derived<RangePresetId>(forceCustom ? 'custom' : detectPreset({ from, to }, today));
  const error = $derived(validateRange({ from, to }, { maxDays, today }));
  const presets = $derived(RANGE_PRESETS.filter((p) => p.days <= maxDays));

  function choose(id: string) {
    if (id === 'custom') {
      forceCustom = true;
      return;
    }
    forceCustom = false;
    const range = presetRange(id as RangePreset['id'], today);
    from = range.from;
    to = range.to;
    onchange?.();
  }
</script>

<div class="field">
  <label for="{idPrefix}-preset">{label}</label>
  <select id="{idPrefix}-preset" class="select" value={selected} onchange={(e) => choose(e.currentTarget.value)}>
    {#each presets as preset (preset.id)}
      <option value={preset.id}>{preset.label}</option>
    {/each}
    <option value="custom">Custom range…</option>
  </select>
</div>

{#if selected === 'custom'}
  <div class="field">
    <label for="{idPrefix}-from">From</label>
    <input
      id="{idPrefix}-from"
      class="input"
      type="date"
      bind:value={from}
      max={to || today}
      aria-invalid={error ? 'true' : undefined}
      aria-describedby={error ? `${idPrefix}-error` : undefined}
      onchange={() => onchange?.()}
    />
  </div>
  <div class="field">
    <label for="{idPrefix}-to">To</label>
    <input
      id="{idPrefix}-to"
      class="input"
      type="date"
      bind:value={to}
      min={from}
      max={today}
      aria-invalid={error ? 'true' : undefined}
      aria-describedby={error ? `${idPrefix}-error` : undefined}
      onchange={() => onchange?.()}
    />
  </div>
{/if}

{#if error}
  <p id="{idPrefix}-error" class="field-error range-error" role="alert">{error}</p>
{/if}

<style>
  .range-error {
    flex-basis: 100%;
  }
</style>
