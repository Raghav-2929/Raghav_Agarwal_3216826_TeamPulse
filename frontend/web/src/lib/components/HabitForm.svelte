<script lang="ts">
  import { errorMessage, isApiError } from '$lib/api/errors';
  import type { Category, Frequency, HabitCreate, HabitOut, Visibility } from '$lib/api/types';
  import { CATEGORY_OPTIONS } from '$lib/utils/categories';
  import { hasErrors, validateHabit, type FieldErrors } from '$lib/utils/validation';

  interface Props {
    initial?: HabitOut | null;
    submitLabel?: string;
    onsubmit: (values: HabitCreate) => Promise<void>;
    oncancel?: () => void;
  }

  let { initial = null, submitLabel = 'Save habit', onsubmit, oncancel }: Props = $props();

  const initialValues = () => ({
    title: initial?.title ?? '',
    description: initial?.description ?? '',
    category: (initial?.category ?? 'fitness') as string,
    frequency: (initial?.frequency ?? 'daily') as string,
    target_per_period: initial?.target_per_period ?? 1,
    visibility: (initial?.visibility ?? 'private') as string,
    color: initial?.color ?? '#4F46E5',
  });

  let form = $state(initialValues());
  let errors = $state<FieldErrors>({});
  let serverError = $state('');
  let submitting = $state(false);
  let formEl = $state<HTMLFormElement>();

  // Daily habits always have a target of exactly 1 per day.
  $effect(() => {
    if (form.frequency === 'daily' && form.target_per_period !== 1) form.target_per_period = 1;
  });

  function describedBy(field: string, hint = false) {
    const ids = [];
    if (hint) ids.push(`habit-${field}-hint`);
    if (errors[field]) ids.push(`habit-${field}-error`);
    return ids.length ? ids.join(' ') : undefined;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    serverError = '';
    errors = validateHabit(form);
    if (hasErrors(errors)) {
      queueMicrotask(() => formEl?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus());
      return;
    }
    submitting = true;
    try {
      await onsubmit({
        title: form.title.trim(),
        description: form.description.trim() || null,
        category: form.category as Category,
        frequency: form.frequency as Frequency,
        target_per_period: Number(form.target_per_period),
        visibility: form.visibility as Visibility,
        color: form.color || null,
      });
    } catch (error) {
      if (isApiError(error)) errors = { ...error.fieldErrors };
      serverError = errorMessage(error);
    } finally {
      submitting = false;
    }
  }
</script>

<form class="form card" bind:this={formEl} onsubmit={submit} novalidate aria-busy={submitting}>
  {#if serverError}
    <div class="form-error" role="alert">{serverError}</div>
  {/if}

  <div class="form-grid">
    <div class="field span-2">
      <label for="habit-title">Title <span class="required" aria-hidden="true">*</span></label>
      <input
        id="habit-title"
        name="title"
        class="input"
        bind:value={form.title}
        required
        minlength="3"
        maxlength="80"
        placeholder="e.g. Morning run"
        aria-invalid={errors.title ? 'true' : undefined}
        aria-describedby={describedBy('title')}
      />
      {#if errors.title}<p id="habit-title-error" class="field-error">{errors.title}</p>{/if}
    </div>

    <div class="field span-2">
      <label for="habit-description">Description</label>
      <textarea
        id="habit-description"
        name="description"
        class="textarea"
        bind:value={form.description}
        maxlength="500"
        rows="3"
        aria-invalid={errors.description ? 'true' : undefined}
        aria-describedby={describedBy('description', true)}
      ></textarea>
      <p id="habit-description-hint" class="field-hint">{form.description.length}/500 characters</p>
      {#if errors.description}<p id="habit-description-error" class="field-error">{errors.description}</p>{/if}
    </div>

    <div class="field">
      <label for="habit-category">Activity type <span class="required" aria-hidden="true">*</span></label>
      <select id="habit-category" name="category" class="select" bind:value={form.category} aria-invalid={errors.category ? 'true' : undefined} aria-describedby={describedBy('category')}>
        {#each CATEGORY_OPTIONS as option (option.value)}
          <option value={option.value}>{option.icon} {option.label}</option>
        {/each}
      </select>
      {#if errors.category}<p id="habit-category-error" class="field-error">{errors.category}</p>{/if}
    </div>

    <div class="field">
      <label for="habit-frequency">Frequency <span class="required" aria-hidden="true">*</span></label>
      <select id="habit-frequency" name="frequency" class="select" bind:value={form.frequency} aria-invalid={errors.frequency ? 'true' : undefined}>
        <option value="daily">Daily</option>
        <option value="weekly">Weekly</option>
      </select>
      {#if errors.frequency}<p class="field-error">{errors.frequency}</p>{/if}
    </div>

    <div class="field">
      <label for="habit-target">Target per {form.frequency === 'weekly' ? 'week' : 'day'}</label>
      <input
        id="habit-target"
        name="target_per_period"
        class="input"
        type="number"
        min="1"
        max={form.frequency === 'weekly' ? 7 : 1}
        step="1"
        bind:value={form.target_per_period}
        disabled={form.frequency === 'daily'}
        aria-invalid={errors.target_per_period ? 'true' : undefined}
        aria-describedby={describedBy('target_per_period', true)}
      />
      <p id="habit-target_per_period-hint" class="field-hint">
        {form.frequency === 'weekly' ? 'How many days per week (1–7).' : 'Daily habits are completed once per day.'}
      </p>
      {#if errors.target_per_period}<p id="habit-target_per_period-error" class="field-error">{errors.target_per_period}</p>{/if}
    </div>

    <div class="field">
      <label for="habit-visibility">Visibility</label>
      <select id="habit-visibility" name="visibility" class="select" bind:value={form.visibility} aria-describedby="habit-visibility-hint">
        <option value="private">🔒 Private — only me</option>
        <option value="team">🤝 Team — teammates can see it</option>
      </select>
      <p id="habit-visibility-hint" class="field-hint">Teammates only ever see the habit itself, never your activity log.</p>
    </div>

    <div class="field">
      <label for="habit-color">Colour</label>
      <div class="row">
        <input id="habit-color" name="color" class="color" type="color" bind:value={form.color} aria-invalid={errors.color ? 'true' : undefined} />
        <code class="small">{form.color}</code>
      </div>
      {#if errors.color}<p class="field-error">{errors.color}</p>{/if}
    </div>
  </div>

  <div class="form-actions">
    {#if oncancel}
      <button type="button" class="btn" onclick={oncancel} disabled={submitting}>Cancel</button>
    {/if}
    <button type="submit" class="btn btn-primary" disabled={submitting}>{submitting ? 'Saving…' : submitLabel}</button>
  </div>
</form>

<style>
  .color {
    width: 3rem;
    height: 2.5rem;
    padding: 2px;
    border: 1px solid var(--tp-color-border-strong);
    border-radius: var(--tp-radius-md);
    background: var(--tp-color-surface);
    cursor: pointer;
  }
</style>
