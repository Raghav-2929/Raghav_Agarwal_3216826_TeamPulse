/**
 * Authentication / session state (Svelte 5 runes).
 *
 * Token storage trade-off:
 *  - The short-lived access token (15 min) lives ONLY in memory, so it is never persisted and an
 *    XSS payload cannot lift it from storage after the tab closes.
 *  - The refresh token is kept in `localStorage` so a reload (or a new tab) can restore the session
 *    via `POST /auth/refresh`. This is readable by any script on the origin, so it is mitigated by
 *    rotation on every refresh (server-side), revocation on logout, a strict CSP on CloudFront, and
 *    no third-party scripts. The stronger alternative — an `HttpOnly; Secure; SameSite=Strict`
 *    refresh cookie set by the gateway — needs a backend change and is the recommended hardening.
 */
import { api, http } from '$lib/api';
import { decodeJwt } from '$lib/api/jwt';
import { isApiError } from '$lib/api/errors';
import type { AccessTokenClaims, Role, TokenResponse, UserOut } from '$lib/api/types';

export const REFRESH_TOKEN_KEY = 'teampulse.refresh_token';

function readRefreshToken(): string | null {
  try {
    return typeof localStorage === 'undefined' ? null : localStorage.getItem(REFRESH_TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeRefreshToken(token: string | null): void {
  try {
    if (typeof localStorage === 'undefined') return;
    if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
    else localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    /* storage unavailable (private mode) — session simply won't survive a reload */
  }
}

class SessionStore {
  user = $state<UserOut | null>(null);
  accessToken = $state<string | null>(null);
  /** Set when the session ended involuntarily (shown on the login page). */
  expiredNotice = $state(false);

  claims = $derived(decodeJwt<AccessTokenClaims>(this.accessToken));
  role = $derived<Role | null>(this.user?.role ?? this.claims?.role ?? null);
  isAuthenticated = $derived(!!this.user && !!this.accessToken);
  isEmployee = $derived(this.role === 'employee');
  isManager = $derived(this.role === 'manager');
  isAdmin = $derived(this.role === 'admin');
  /** Managers and admins may view aggregated team insights and create challenges. */
  isLead = $derived(this.role === 'manager' || this.role === 'admin');
  /** Teams this user manages — only available from the access-token claims (`UserOut` lacks it). */
  managedTeamIds = $derived<string[]>(this.claims?.managed_team_ids ?? []);

  #refreshing: Promise<boolean> | null = null;

  constructor() {
    http.setAuth({
      getAccessToken: () => this.accessToken,
      refresh: () => this.refresh(),
      onAuthFailure: () => this.handleAuthFailure(),
    });
    if (typeof window !== 'undefined') {
      // Signing out in another tab removes the shared refresh token → end this tab's session too.
      window.addEventListener('storage', (event) => {
        if (event.key === REFRESH_TOKEN_KEY && event.newValue === null && this.user) {
          this.accessToken = null;
          this.user = null;
          this.#redirectToLogin();
        }
      });
    }
  }

  hasRole(...roles: Role[]): boolean {
    return !!this.role && roles.includes(this.role);
  }

  async login(email: string, password: string): Promise<UserOut> {
    const tokens = await api.auth.login({ email: email.trim(), password });
    this.#apply(tokens);
    this.expiredNotice = false;
    return tokens.user;
  }

  /**
   * Makes sure there is a usable session, restoring it from the stored refresh token after a
   * reload. Resolves `false` when the user must sign in.
   */
  async ensure(): Promise<boolean> {
    if (this.isAuthenticated) return true;
    if (!readRefreshToken()) return false;
    return this.refresh();
  }

  /**
   * Rotates tokens with the stored refresh token. Concurrent callers in this tab share one request,
   * and the Web Locks API serialises refreshes across tabs so two tabs never spend the same
   * (single-use, rotating) refresh token — the second tab reads the already-rotated one.
   */
  refresh(): Promise<boolean> {
    if (this.#refreshing) return this.#refreshing;
    const run = async (): Promise<boolean> => {
      const refreshToken = readRefreshToken();
      if (!refreshToken) return false;
      try {
        this.#apply(await api.auth.refresh(refreshToken));
        return true;
      } catch (error) {
        // Invalid/expired/revoked refresh token → drop it (unless another tab already replaced it).
        // Network errors keep it for a later retry.
        const networkError = isApiError(error) && error.status === 0;
        if (!networkError && readRefreshToken() === refreshToken) this.#clear();
        else if (!networkError) {
          this.accessToken = null;
          this.user = null;
        }
        return false;
      }
    };
    const locks = typeof navigator !== 'undefined' ? navigator.locks : undefined;
    // (`.then` flattens lib.dom's Promise<Promise<boolean>> typing of `request`.)
    const exclusive: Promise<boolean> = locks?.request ? locks.request('teampulse.auth.refresh', run).then((ok) => ok) : run();
    const pending = exclusive.finally(() => {
      this.#refreshing = null;
    });
    this.#refreshing = pending;
    return pending;
  }

  async logout(): Promise<void> {
    const refreshToken = readRefreshToken();
    try {
      if (refreshToken && this.accessToken) await api.auth.logout(refreshToken);
    } catch {
      /* best effort — the local session is cleared regardless */
    } finally {
      this.#clear();
    }
  }

  /** Replaces the cached user (e.g. after a profile update). */
  setUser(user: UserOut): void {
    this.user = user;
  }

  /** The session could not be recovered (refresh failed / repeated 401): sign out and go to /login. */
  handleAuthFailure(): void {
    const wasSignedIn = !!this.user;
    this.#clear();
    if (wasSignedIn) this.expiredNotice = true;
    this.#redirectToLogin();
  }

  #redirectToLogin(): void {
    if (typeof window === 'undefined' || window.location.pathname.startsWith('/login')) return;
    const target = `${window.location.pathname}${window.location.search}`;
    // Lazy import avoids a hard dependency on the router in non-browser contexts (tests).
    void import('$app/navigation').then(({ goto }) => goto(`/login?redirect=${encodeURIComponent(target)}`, { replaceState: true }));
  }

  #apply(tokens: TokenResponse): void {
    this.accessToken = tokens.access_token;
    this.user = tokens.user;
    writeRefreshToken(tokens.refresh_token);
  }

  #clear(): void {
    this.accessToken = null;
    this.user = null;
    writeRefreshToken(null);
  }
}

export const session = new SessionStore();
