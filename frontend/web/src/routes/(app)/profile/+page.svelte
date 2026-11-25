<script lang="ts">
  import { api } from '$lib/api';
  import { errorMessage, isApiError } from '$lib/api/errors';
  import PageHeader from '$lib/components/PageHeader.svelte';
  import { session } from '$lib/state/session.svelte';
  import { toasts } from '$lib/state/toasts.svelte';
  import { formatDate } from '$lib/utils/dates';
  import { ROLE_LABELS } from '$lib/utils/nav';
  import { hasErrors, validateFullName, validatePasswordChange, type FieldErrors } from '$lib/utils/validation';

  const initialName = () => session.user?.full_name ?? '';
  let fullName = $state(initialName());
  let nameError = $state('');
  let savingName = $state(false);

  let pw = $state({ current: '', next: '', confirm: '' });
  let pwErrors = $state<FieldErrors>({});
  let pwError = $state('');
  let savingPw = $state(false);

  async function saveName(event: SubmitEvent) {
    event.preventDefault();
    nameError = validateFullName(fullName) ?? '';
    if (nameError) return;
    savingName = true;
    try {
      const user = await api.users.updateMe({ full_name: fullName.trim() });
      session.setUser(user);
      fullName = user.full_name;
      toasts.success('Your name was updated.');
    } catch (error) {
      nameError = isApiError(error) ? (error.fieldErrors.full_name ?? error.detail) : errorMessage(error);
    } finally {
      savingName = false;
    }
  }

  async function changePassword(event: SubmitEvent) {
    event.preventDefault();
    pwError = '';
    pwErrors = validatePasswordChange(pw);
    if (hasErrors(pwErrors)) return;
    savingPw = true;
    try {
      await api.users.changePassword({ current_password: pw.current, new_password: pw.next });
      pw = { current: '', next: '', confirm: '' };
      toasts.success('Password changed.');
    } catch (error) {
      if (isApiError(error)) {
        pwErrors = {};
        if (error.fieldErrors.current_password) pwErrors.current = error.fieldErrors.current_password;
        if (error.fieldErrors.new_password) pwErrors.next = error.fieldErrors.new_password;
      }
      pwError = errorMessage(error);
    } finally {
      savingPw = false;
    }
  }
</script>

<svelte:head>
  <title>Profile · TeamPulse</title>
</svelte:head>

<PageHeader title="Profile" description="Your account details and security settings." />

<div class="layout">
  <section class="card" aria-labelledby="account-title">
    <h2 id="account-title" class="section-title">Account</h2>
    <dl class="kv">
      <dt>Email</dt>
      <dd>{session.user?.email}</dd>
      <dt>Role</dt>
      <dd>{session.role ? ROLE_LABELS[session.role] : ''}</dd>
      <dt>Team</dt>
      <dd>{session.user?.team_name ?? '—'}</dd>
      <dt>Member since</dt>
      <dd>{formatDate(session.user?.created_at)}</dd>
    </dl>

    <hr class="divider" />

    <form class="form" onsubmit={saveName} novalidate>
      <div class="field">
        <label for="profile-name">Display name</label>
        <input
          id="profile-name"
          class="input"
          bind:value={fullName}
          autocomplete="name"
          maxlength="120"
          aria-invalid={nameError ? 'true' : undefined}
          aria-describedby={nameError ? 'profile-name-error' : undefined}
        />
        {#if nameError}<p id="profile-name-error" class="field-error" role="alert">{nameError}</p>{/if}
      </div>
      <div class="form-actions">
        <button type="submit" class="btn btn-primary" disabled={savingName || fullName.trim() === session.user?.full_name}>
          {savingName ? 'Saving…' : 'Save name'}
        </button>
      </div>
    </form>
  </section>

  <section class="card" aria-labelledby="password-title">
    <h2 id="password-title" class="section-title">Change password</h2>
    <form class="form" onsubmit={changePassword} novalidate>
      {#if pwError}<div class="form-error" role="alert">{pwError}</div>{/if}
      <div class="field">
        <label for="pw-current">Current password</label>
        <input id="pw-current" class="input" type="password" autocomplete="current-password" bind:value={pw.current} aria-invalid={pwErrors.current ? 'true' : undefined} aria-describedby={pwErrors.current ? 'pw-current-error' : undefined} />
        {#if pwErrors.current}<p id="pw-current-error" class="field-error">{pwErrors.current}</p>{/if}
      </div>
      <div class="field">
        <label for="pw-new">New password</label>
        <input id="pw-new" class="input" type="password" autocomplete="new-password" bind:value={pw.next} aria-invalid={pwErrors.next ? 'true' : undefined} aria-describedby="pw-new-hint{pwErrors.next ? ' pw-new-error' : ''}" />
        <p id="pw-new-hint" class="field-hint">At least 8 characters, including upper-case, lower-case and a digit.</p>
        {#if pwErrors.next}<p id="pw-new-error" class="field-error">{pwErrors.next}</p>{/if}
      </div>
      <div class="field">
        <label for="pw-confirm">Confirm new password</label>
        <input id="pw-confirm" class="input" type="password" autocomplete="new-password" bind:value={pw.confirm} aria-invalid={pwErrors.confirm ? 'true' : undefined} aria-describedby={pwErrors.confirm ? 'pw-confirm-error' : undefined} />
        {#if pwErrors.confirm}<p id="pw-confirm-error" class="field-error">{pwErrors.confirm}</p>{/if}
      </div>
      <div class="form-actions">
        <button type="submit" class="btn btn-primary" disabled={savingPw}>{savingPw ? 'Updating…' : 'Change password'}</button>
      </div>
    </form>
  </section>
</div>

<style>
  .layout {
    display: grid;
    gap: var(--tp-space-5);
    grid-template-columns: repeat(2, minmax(0, 1fr));
    align-items: start;
  }

  @media (max-width: 900px) {
    .layout {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .section-title {
    font-size: var(--tp-font-size-lg);
    margin-bottom: var(--tp-space-4);
  }
</style>
