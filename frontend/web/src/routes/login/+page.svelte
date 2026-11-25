<script lang="ts">
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { errorMessage, isApiError } from '$lib/api/errors';
  import Icon from '$lib/components/Icon.svelte';
  import { DEMO_ACCOUNTS, DEMO_PASSWORD, type DemoAccount } from '$lib/demo-accounts';
  import { session } from '$lib/state/session.svelte';
  import { ROLE_LABELS, safeRedirect } from '$lib/utils/nav';
  import { hasErrors, validateLogin, type FieldErrors } from '$lib/utils/validation';

  let email = $state('');
  let password = $state('');
  let showPassword = $state(false);
  let errors = $state<FieldErrors>({});
  let formError = $state('');
  let submitting = $state(false);
  let emailInput = $state<HTMLInputElement>();
  let passwordInput = $state<HTMLInputElement>();

  const redirectTo = $derived(safeRedirect(page.url.searchParams.get('redirect')));

  async function submit(event: SubmitEvent) {
    event.preventDefault();
    formError = '';
    errors = validateLogin({ email, password });
    if (hasErrors(errors)) {
      (errors.email ? emailInput : passwordInput)?.focus();
      return;
    }
    submitting = true;
    try {
      await session.login(email, password);
      await goto(redirectTo, { replaceState: true });
    } catch (error) {
      if (isApiError(error) && error.code === 'account_locked') {
        formError = error.detail || 'Too many failed attempts. Your account is locked for 15 minutes.';
      } else if (isApiError(error) && error.status === 401) {
        formError = error.detail || 'Incorrect email or password.';
      } else {
        formError = errorMessage(error);
      }
      passwordInput?.focus();
    } finally {
      submitting = false;
    }
  }

  function quickFill(account: DemoAccount) {
    email = account.email;
    password = DEMO_PASSWORD;
    errors = {};
    formError = '';
    passwordInput?.focus();
  }
</script>

<svelte:head>
  <title>Sign in · TeamPulse</title>
</svelte:head>

<main class="login">
  <aside class="hero">
    <div class="hero-brand">
      <span class="hero-logo" aria-hidden="true">
        <svg viewBox="0 0 32 32" width="22" height="22">
          <path d="M4 17h6l3-7 4 13 3-6h8" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </span>
      <span>TeamPulse</span>
    </div>
    <div class="hero-copy">
      <p class="hero-title">Healthy habits, built together.</p>
      <p class="hero-text">Track your wellness habits, join team challenges and follow your progress, while your personal data stays private.</p>
    </div>
    <ul class="list-plain features">
      <li>
        <span class="feature-icon" aria-hidden="true"><Icon name="check" /></span>
        <span><strong>Habits and streaks</strong><span>Log a habit in one click and watch your streak grow.</span></span>
      </li>
      <li>
        <span class="feature-icon" aria-hidden="true"><Icon name="trophy" /></span>
        <span><strong>Team challenges</strong><span>Compete on live leaderboards and earn badges.</span></span>
      </li>
      <li>
        <span class="feature-icon" aria-hidden="true"><Icon name="shield" /></span>
        <span><strong>Private by design</strong><span>Managers only see anonymised team trends.</span></span>
      </li>
    </ul>
  </aside>

  <div class="forms">
    <section class="panel card" aria-labelledby="login-title">
      <div class="brand">
        <svg viewBox="0 0 32 32" width="40" height="40" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="var(--tp-color-primary)" />
          <path d="M5 17h6l3-7 4 13 3-6h6" fill="none" stroke="var(--tp-color-primary-contrast)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div>
          <h1 id="login-title">Sign in to TeamPulse</h1>
          <p class="muted small">Build healthy habits together.</p>
        </div>
      </div>

      {#if session.expiredNotice}
        <div class="notice notice-warning" role="status">
          <span class="notice-icon" aria-hidden="true">⏱️</span>
          <p>Your session expired. Please sign in again.</p>
        </div>
      {/if}

      <form class="form" onsubmit={submit} novalidate aria-busy={submitting}>
        {#if formError}
          <div class="form-error" role="alert">{formError}</div>
        {/if}

        <div class="field">
          <label for="email">Work email</label>
          <input
            id="email"
            name="email"
            class="input"
            type="email"
            autocomplete="username"
            bind:value={email}
            bind:this={emailInput}
            required
            aria-invalid={errors.email ? 'true' : undefined}
            aria-describedby={errors.email ? 'email-error' : undefined}
          />
          {#if errors.email}<p id="email-error" class="field-error">{errors.email}</p>{/if}
        </div>

        <div class="field">
          <label for="password">Password</label>
          <div class="password">
            <input
              id="password"
              name="password"
              class="input"
              type={showPassword ? 'text' : 'password'}
              autocomplete="current-password"
              bind:value={password}
              bind:this={passwordInput}
              required
              aria-invalid={errors.password ? 'true' : undefined}
              aria-describedby={errors.password ? 'password-error' : undefined}
            />
            <button type="button" class="btn btn-ghost btn-sm toggle" aria-pressed={showPassword} onclick={() => (showPassword = !showPassword)}>
              {showPassword ? 'Hide' : 'Show'}
            </button>
          </div>
          {#if errors.password}<p id="password-error" class="field-error">{errors.password}</p>{/if}
        </div>

        <button type="submit" class="btn btn-primary submit" disabled={submitting}>{submitting ? 'Signing in…' : 'Sign in'}</button>
      </form>
    </section>

    <section class="demo card" aria-labelledby="demo-title">
      <h2 id="demo-title">Demo accounts</h2>
      <p class="small muted">Click an account to fill the form. Every demo password is <code>{DEMO_PASSWORD}</code>.</p>
      <ul class="list-plain accounts">
        {#each DEMO_ACCOUNTS as account (account.email)}
          <li>
            <button type="button" class="account" onclick={() => quickFill(account)} aria-label="Use demo account {account.email} ({ROLE_LABELS[account.role]})">
              <span class="pill {account.role === 'admin' ? 'pill-danger' : account.role === 'manager' ? 'pill-primary' : ''}">{ROLE_LABELS[account.role]}</span>
              <span class="email">{account.email}</span>
              <span class="team xsmall muted">{account.team ?? 'Organisation'}</span>
            </button>
          </li>
        {/each}
      </ul>
    </section>
  </div>
</main>

<style>
  .login {
    min-height: 100vh;
    display: grid;
    grid-template-columns: minmax(0, 34rem) minmax(0, 30rem);
    justify-content: center;
    align-items: start;
    gap: var(--tp-space-6);
    padding: var(--tp-space-6);
  }

  @media (max-width: 1100px) {
    .login {
      grid-template-columns: minmax(0, 30rem);
      padding: clamp(var(--tp-space-4), 6vh, var(--tp-space-12)) var(--tp-space-4);
    }

    .hero {
      display: none !important;
    }
  }

  /* ---------- brand panel */

  .hero {
    position: sticky;
    top: var(--tp-space-6);
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-8);
    min-height: calc(100vh - 2 * var(--tp-space-6));
    padding: var(--tp-space-10) var(--tp-space-8) var(--tp-space-8);
    overflow: hidden;
    border-radius: var(--tp-radius-xl);
    background:
      radial-gradient(30rem 22rem at 105% -5%, rgb(255 255 255 / 0.28), transparent 60%),
      radial-gradient(26rem 20rem at -5% 105%, rgb(167 139 250 / 0.55), transparent 60%),
      var(--tp-gradient-primary);
    color: var(--tp-color-primary-contrast);
    box-shadow: var(--tp-shadow-lg);
  }

  .hero-brand {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
    font-size: var(--tp-font-size-lg);
    font-weight: var(--tp-font-weight-bold);
    letter-spacing: -0.02em;
  }

  .hero-logo {
    display: grid;
    place-items: center;
    width: 2.5rem;
    height: 2.5rem;
    border-radius: var(--tp-radius-md);
    background: rgb(255 255 255 / 0.2);
    border: 1px solid rgb(255 255 255 / 0.3);
  }

  .hero-copy {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-4);
    margin-top: auto;
  }

  .hero-title {
    max-width: 22rem;
    font-size: clamp(2.1rem, 3.2vw, 2.75rem);
    font-weight: var(--tp-font-weight-bold);
    line-height: 1.08;
    letter-spacing: -0.035em;
  }

  .hero-text {
    max-width: 26rem;
    font-size: var(--tp-font-size-md);
    opacity: 0.92;
  }

  .features {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-3);
  }

  .features li {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
    padding: var(--tp-space-3) var(--tp-space-4);
    border-radius: var(--tp-radius-lg);
    background: rgb(255 255 255 / 0.14);
    border: 1px solid rgb(255 255 255 / 0.24);
    -webkit-backdrop-filter: blur(12px);
    backdrop-filter: blur(12px);
  }

  .features li > span:last-child {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: var(--tp-font-size-sm);
    opacity: 0.95;
  }

  .features strong {
    font-size: var(--tp-font-size-sm);
  }

  .feature-icon {
    display: grid;
    place-items: center;
    flex: none;
    width: 2.5rem;
    height: 2.5rem;
    border-radius: var(--tp-radius-md);
    background: rgb(255 255 255 / 0.2);
  }

  /* ---------- sign-in + demo accounts */

  .forms {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-5);
    min-width: 0;
  }

  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-5);
    padding: var(--tp-space-8);
  }

  @media (max-width: 640px) {
    .panel {
      padding: var(--tp-space-6) var(--tp-space-5);
    }
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--tp-space-3);
  }

  .brand svg {
    filter: drop-shadow(0 6px 10px rgb(37 99 235 / 0.35));
  }

  .brand h1 {
    font-size: var(--tp-font-size-xl);
  }

  .password {
    position: relative;
  }

  .password .input {
    padding-right: 4.5rem;
  }

  .toggle {
    position: absolute;
    right: 6px;
    top: 50%;
    transform: translateY(-50%);
  }

  .toggle:active:not(:disabled) {
    transform: translateY(-50%);
  }

  .submit {
    width: 100%;
    min-height: 2.875rem;
    font-size: var(--tp-font-size-md);
  }

  .demo {
    display: flex;
    flex-direction: column;
    gap: var(--tp-space-3);
  }

  .demo h2 {
    font-size: var(--tp-font-size-lg);
  }

  .accounts {
    display: grid;
    gap: 2px;
    margin-top: var(--tp-space-1);
  }

  .account {
    display: grid;
    grid-template-columns: 5.5rem 1fr auto;
    align-items: center;
    gap: var(--tp-space-3);
    width: 100%;
    padding: var(--tp-space-2) var(--tp-space-3);
    border: 1px solid transparent;
    border-radius: var(--tp-radius-md);
    background: transparent;
    color: var(--tp-color-text);
    font: inherit;
    font-size: var(--tp-font-size-sm);
    text-align: left;
    cursor: pointer;
    transition:
      background var(--tp-duration-fast) var(--tp-easing-standard),
      border-color var(--tp-duration-fast) var(--tp-easing-standard);
  }

  .account:hover {
    background: var(--tp-glass-bg-strong);
    border-color: var(--tp-glass-border);
    box-shadow: var(--tp-shadow-sm);
  }

  .account .pill {
    justify-content: center;
  }

  .email {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
