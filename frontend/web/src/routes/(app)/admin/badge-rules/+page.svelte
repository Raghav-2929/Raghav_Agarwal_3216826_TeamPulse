<script lang="ts">
  import { api } from '$lib/api';
  import { errorMessage, isApiError } from '$lib/api/errors';
  import { BADGE_CRITERIA, type BadgeCriterion, type BadgeRuleOut, type Category } from '$lib/api/types';
  import ConfirmDialog from '$lib/components/ConfirmDialog.svelte';
  import EmptyState from '$lib/components/EmptyState.svelte';
  import ErrorState from '$lib/components/ErrorState.svelte';
  import Loading from '$lib/components/Loading.svelte';
  import Modal from '$lib/components/Modal.svelte';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { createQuery } from '$lib/state/query.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { CATEGORY_OPTIONS, categoryLabel } from '$lib/utils/categories';
  import { hasErrors, validateBadgeRule, type FieldErrors } from '$lib/utils/validation';

  const CRITERION_LABELS: Record<BadgeCriterion, string> = {
    streak_days: 'Streak length (days)',
    total_completions: 'Total completions',
    category_completions: 'Completions in a category',
  };

  const rules = createQuery({ key: () => 'rules', fetch: (_k, signal) => api.badgeRules.list({ signal }) });

  let open = $state(false);
  let editing = $state<BadgeRuleOut | null>(null);
  let form = $state({ code: '', name: '', description: '', icon: '🏅', criterion: 'streak_days', category: '', threshold: 7, is_active: true });
  let errors = $state<FieldErrors>({});
  let formError = $state('');
  let saving = $state(false);

  let deleteTarget = $state<BadgeRuleOut | null>(null);
  let deleteOpen = $state(false);

  function openCreate() {
    editing = null;
    form = { code: '', name: '', description: '', icon: '🏅', criterion: 'streak_days', category: '', threshold: 7, is_active: true };
    errors = {};
    formError = '';
    open = true;
  }

  function openEdit(rule: BadgeRuleOut) {
    editing = rule;
    form = { ...rule, category: rule.category ?? '' };
    errors = {};
    formError = '';
    open = true;
  }

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    formError = '';
    errors = validateBadgeRule(form);
    if (hasErrors(errors)) return;
    saving = true;
    try {
      // PUT /badge-rules/{code} is an upsert; the body is BadgeRuleOut minus `code`.
      const saved = await api.badgeRules.upsert(form.code, {
        name: form.name.trim(),
        description: form.description.trim(),
        icon: form.icon.trim(),
        criterion: form.criterion as BadgeCriterion,
        category: form.criterion === 'category_completions' || form.category ? ((form.category || null) as Category | null) : null,
        threshold: Number(form.threshold),
        is_active: form.is_active,
      });
      toasts.success(`${editing ? 'Updated' : 'Created'} badge “${saved?.name ?? form.name}”.`);
      open = false;
      rules.refetch();
    } catch (error) {
      if (isApiError(error)) errors = { ...error.fieldErrors };
      formError = errorMessage(error);
    } finally {
      saving = false;
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    saving = true;
    try {
      await api.badgeRules.remove(deleteTarget.code);
      toasts.success(`Deleted badge rule “${deleteTarget.name}”.`);
      deleteOpen = false;
      rules.refetch();
    } catch (error) {
      toasts.error(error);
    } finally {
      saving = false;
    }
  }
</script>

<svelte:head>
  <title>Badge rules · Admin · TeamPulse</title>
</svelte:head>

<PageHeader title="Badge rules" description="Define the achievements the streak processor awards. Changes propagate to the processor automatically.">
  {#snippet actions()}
    <button type="button" class="btn btn-primary" onclick={openCreate}>+ New rule</button>
  {/snippet}
</PageHeader>

{#if rules.initialLoading}
  <Loading label="Loading badge rules…" />
{:else if rules.error}
  <ErrorState error={rules.error} retry={rules.refetch} />
{:else if (rules.data?.length ?? 0) === 0}
  <EmptyState icon="🎖️" title="No badge rules" message="Create a rule to start rewarding healthy habits.">
    <button type="button" class="btn btn-primary" onclick={openCreate}>Create rule</button>
  </EmptyState>
{:else}
  <div class="table-wrap">
    <table class="table">
      <caption class="sr-only">Badge rules</caption>
      <thead>
        <tr>
          <th scope="col">Badge</th>
          <th scope="col">Code</th>
          <th scope="col">Criterion</th>
          <th scope="col">Category</th>
          <th scope="col">Threshold</th>
          <th scope="col">Status</th>
          <th scope="col" class="actions"><span class="sr-only">Actions</span></th>
        </tr>
      </thead>
      <tbody>
        {#each rules.data ?? [] as rule (rule.code)}
          <tr>
            <td>
              <span class="badge-cell"><span class="icon" aria-hidden="true">{rule.icon}</span><span><strong>{rule.name}</strong><br /><span class="xsmall muted">{rule.description}</span></span></span>
            </td>
            <td><code class="small">{rule.code}</code></td>
            <td class="small">{CRITERION_LABELS[rule.criterion] ?? rule.criterion}</td>
            <td class="small">{rule.category ? categoryLabel(rule.category) : '—'}</td>
            <td class="num">{rule.threshold}</td>
            <td>{#if rule.is_active}<span class="pill pill-success">Active</span>{:else}<span class="pill">Disabled</span>{/if}</td>
            <td class="actions">
              <button type="button" class="btn btn-sm" onclick={() => openEdit(rule)} aria-label="Edit {rule.name}">Edit</button>
              <button
                type="button"
                class="btn btn-sm btn-ghost"
                onclick={() => {
                  deleteTarget = rule;
                  deleteOpen = true;
                }}
                aria-label="Delete {rule.name}">Delete</button
              >
            </td>
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<Modal bind:open title={editing ? `Edit ${editing.name}` : 'New badge rule'} size="lg">
  <form id="badge-form" class="form" onsubmit={submit} novalidate>
    {#if formError}<div class="form-error" role="alert">{formError}</div>{/if}
    <div class="form-grid">
      <div class="field">
        <label for="rule-code">Code</label>
        <input id="rule-code" class="input" bind:value={form.code} disabled={!!editing} placeholder="week_warrior" aria-invalid={errors.code ? 'true' : undefined} aria-describedby="rule-code-hint" />
        <p id="rule-code-hint" class="field-hint">Stable identifier — cannot be changed later.</p>
        {#if errors.code}<p class="field-error">{errors.code}</p>{/if}
      </div>
      <div class="field">
        <label for="rule-icon">Icon (emoji)</label>
        <input id="rule-icon" class="input" bind:value={form.icon} maxlength="8" aria-invalid={errors.icon ? 'true' : undefined} />
        {#if errors.icon}<p class="field-error">{errors.icon}</p>{/if}
      </div>
      <div class="field">
        <label for="rule-name">Name</label>
        <input id="rule-name" class="input" bind:value={form.name} maxlength="60" aria-invalid={errors.name ? 'true' : undefined} />
        {#if errors.name}<p class="field-error">{errors.name}</p>{/if}
      </div>
      <div class="field">
        <label for="rule-threshold">Threshold</label>
        <input id="rule-threshold" class="input" type="number" min="1" step="1" bind:value={form.threshold} aria-invalid={errors.threshold ? 'true' : undefined} />
        {#if errors.threshold}<p class="field-error">{errors.threshold}</p>{/if}
      </div>
      <div class="field span-2">
        <label for="rule-description">Description</label>
        <input id="rule-description" class="input" bind:value={form.description} maxlength="200" />
      </div>
      <div class="field">
        <label for="rule-criterion">Criterion</label>
        <select id="rule-criterion" class="select" bind:value={form.criterion}>
          {#each BADGE_CRITERIA as criterion (criterion)}<option value={criterion}>{CRITERION_LABELS[criterion]}</option>{/each}
        </select>
      </div>
      <div class="field">
        <label for="rule-category">Category</label>
        <select id="rule-category" class="select" bind:value={form.category} aria-invalid={errors.category ? 'true' : undefined}>
          <option value="">{form.criterion === 'category_completions' ? 'Choose a category' : 'Any'}</option>
          {#each CATEGORY_OPTIONS as option (option.value)}<option value={option.value}>{option.icon} {option.label}</option>{/each}
        </select>
        {#if errors.category}<p class="field-error">{errors.category}</p>{/if}
      </div>
    </div>
    <label class="checkbox"><input type="checkbox" bind:checked={form.is_active} /> Active</label>
    <div class="preview">
      <span class="small muted">Preview</span>
      <tp-badge icon={form.icon} name={form.name || 'Badge name'} description={form.description} locked={!form.is_active}></tp-badge>
    </div>
  </form>
  {#snippet footer()}
    <button type="button" class="btn" onclick={() => (open = false)}>Cancel</button>
    <button type="submit" form="badge-form" class="btn btn-primary" disabled={saving}>{saving ? 'Saving…' : 'Save rule'}</button>
  {/snippet}
</Modal>

<ConfirmDialog
  bind:open={deleteOpen}
  title="Delete badge rule?"
  message="“{deleteTarget?.name}” will no longer be awarded. Badges already earned are kept."
  confirmLabel="Delete"
  danger
  busy={saving}
  onconfirm={confirmDelete}
/>

<style>
  .badge-cell {
    display: flex;
    gap: var(--tp-space-3);
    align-items: center;
  }

  .icon {
    font-size: 1.5rem;
  }

  .preview {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-2);
    max-width: 12rem;
  }
</style>
