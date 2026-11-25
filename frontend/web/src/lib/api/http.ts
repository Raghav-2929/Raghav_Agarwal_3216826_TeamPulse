import { ApiError, parseErrorResponse } from './errors';

export type QueryValue = string | number | boolean | null | undefined;
export type Query = Record<string, QueryValue>;

/** Hooks the session store installs so the client can authenticate and self-heal on 401. */
export interface AuthHooks {
  /** Current in-memory access token (or null). */
  getAccessToken(): string | null;
  /** Attempts a token refresh; resolves `true` when a fresh access token is available. */
  refresh(): Promise<boolean>;
  /** Called once the session cannot be recovered (refresh failed / repeated 401). */
  onAuthFailure(): void;
}

export interface RequestOptions {
  query?: Query;
  body?: unknown;
  signal?: AbortSignal;
  /** Attach the bearer token (default true). Public endpoints pass false. */
  auth?: boolean;
  /** On 401, refresh the session once and retry (default true when `auth`). */
  retryOnUnauthorized?: boolean;
  headers?: Record<string, string>;
}

export interface HttpClient {
  request<T>(method: string, path: string, options?: RequestOptions): Promise<T>;
  get<T>(path: string, options?: Omit<RequestOptions, 'body'>): Promise<T>;
  post<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T>;
  put<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T>;
  patch<T>(path: string, body?: unknown, options?: RequestOptions): Promise<T>;
  delete<T = void>(path: string, options?: RequestOptions): Promise<T>;
  setAuth(hooks: AuthHooks): void;
  readonly baseUrl: string;
}

const NO_AUTH: AuthHooks = {
  getAccessToken: () => null,
  refresh: async () => false,
  onAuthFailure: () => {},
};

/**
 * Joins base URL, path and query string. `undefined`, `null` and `''` query values are dropped,
 * booleans are serialised as `true`/`false`.
 */
export function buildUrl(baseUrl: string, path: string, query?: Query): string {
  const base = (baseUrl ?? '').replace(/\/+$/, '');
  const cleanPath = path.startsWith('/') ? path : `/${path}`;
  const params = new URLSearchParams();
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value === undefined || value === null || value === '') continue;
      params.append(key, String(value));
    }
  }
  const qs = params.toString();
  return `${base}${cleanPath}${qs ? `?${qs}` : ''}`;
}

export function newRequestId(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c && typeof c.randomUUID === 'function') return c.randomUUID();
  return `req-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function isAbortError(error: unknown): boolean {
  return (
    (typeof DOMException !== 'undefined' && error instanceof DOMException && error.name === 'AbortError') ||
    (error instanceof Error && error.name === 'AbortError')
  );
}

export function createHttpClient(config: { baseUrl?: string; fetch?: typeof fetch; auth?: AuthHooks } = {}): HttpClient {
  const baseUrl = config.baseUrl ?? '';
  let hooks: AuthHooks = config.auth ?? NO_AUTH;
  const fetchImpl = (...args: Parameters<typeof fetch>) => (config.fetch ?? globalThis.fetch)(...args);

  async function request<T>(method: string, path: string, options: RequestOptions = {}, isRetry = false): Promise<T> {
    const useAuth = options.auth !== false;
    const headers: Record<string, string> = {
      Accept: 'application/json, application/problem+json',
      'X-Request-ID': newRequestId(),
      ...options.headers,
    };
    let body: string | undefined;
    if (options.body !== undefined) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(options.body);
    }
    const token = useAuth ? hooks.getAccessToken() : null;
    if (token) headers.Authorization = `Bearer ${token}`;

    let response: Response;
    try {
      response = await fetchImpl(buildUrl(baseUrl, path, options.query), {
        method,
        headers,
        body,
        signal: options.signal,
        credentials: 'same-origin',
      });
    } catch (error) {
      if (isAbortError(error)) throw error;
      throw new ApiError({ status: 0 });
    }

    if (response.status === 401 && useAuth) {
      const mayRetry = options.retryOnUnauthorized !== false && !isRetry;
      if (mayRetry) {
        const refreshed = await hooks.refresh().catch(() => false);
        if (refreshed) return request<T>(method, path, options, true);
      }
      const error = await parseErrorResponse(response);
      if (options.retryOnUnauthorized !== false) hooks.onAuthFailure();
      throw error;
    }

    if (!response.ok) throw await parseErrorResponse(response);
    if (response.status === 204 || response.status === 205) return undefined as T;

    const text = await response.text();
    if (!text) return undefined as T;
    try {
      return JSON.parse(text) as T;
    } catch {
      throw new ApiError({ status: response.status, detail: 'The server returned an unreadable response.' });
    }
  }

  return {
    baseUrl,
    request,
    get: (path, options) => request('GET', path, options),
    post: (path, body, options) => request('POST', path, { ...options, body }),
    put: (path, body, options) => request('PUT', path, { ...options, body }),
    patch: (path, body, options) => request('PATCH', path, { ...options, body }),
    delete: (path, options) => request('DELETE', path, options),
    setAuth(next) {
      hooks = next;
    },
  };
}
