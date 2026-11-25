import { describe, expect, it, vi } from 'vitest';
import { ApiError } from './errors';
import { buildUrl, createHttpClient, type AuthHooks } from './http';

function json(status: number, body: unknown, type = 'application/json') {
  return new Response(body === undefined ? null : JSON.stringify(body), { status, headers: { 'content-type': type } });
}

function authHooks(overrides: Partial<AuthHooks> = {}): AuthHooks & { token: string } {
  const state = { token: 'old-token' };
  return Object.assign(state, {
    getAccessToken: () => state.token,
    refresh: vi.fn(async () => {
      state.token = 'new-token';
      return true;
    }),
    onAuthFailure: vi.fn(),
    ...overrides,
  });
}

describe('buildUrl', () => {
  it('joins base, path and drops empty query values', () => {
    expect(buildUrl('', '/api/v1/habits', { search: 'run', category: '', page: 2, include_archived: false, x: undefined, y: null })).toBe(
      '/api/v1/habits?search=run&page=2&include_archived=false',
    );
    expect(buildUrl('https://api.example.com/', 'api/v1/x')).toBe('https://api.example.com/api/v1/x');
  });
});

describe('HTTP client', () => {
  it('attaches the bearer token, JSON body and a request id', async () => {
    const fetch = vi.fn(async () => json(201, { id: '1' }));
    const client = createHttpClient({ fetch, auth: authHooks() });
    const result = await client.post<{ id: string }>('/api/v1/habits', { title: 'Run' });
    expect(result).toEqual({ id: '1' });
    const [url, init] = fetch.mock.calls[0] as unknown as [string, RequestInit];
    const headers = init.headers as Record<string, string>;
    expect(url).toBe('/api/v1/habits');
    expect(init.method).toBe('POST');
    expect(init.body).toBe('{"title":"Run"}');
    expect(headers.Authorization).toBe('Bearer old-token');
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers['X-Request-ID']).toBeTruthy();
  });

  it('does not send the token to public endpoints', async () => {
    const fetch = vi.fn(async () => json(200, {}));
    const client = createHttpClient({ fetch, auth: authHooks() });
    await client.post('/api/v1/auth/login', { email: 'a', password: 'b' }, { auth: false });
    const init = (fetch.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>).Authorization).toBeUndefined();
  });

  it('returns undefined for 204 responses', async () => {
    const client = createHttpClient({ fetch: vi.fn(async () => new Response(null, { status: 204 })), auth: authHooks() });
    await expect(client.delete('/api/v1/habits/1')).resolves.toBeUndefined();
  });

  it('refreshes once on 401 and retries with the new token', async () => {
    const hooks = authHooks();
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(json(401, { status: 401, code: 'token_expired', detail: 'expired' }, 'application/problem+json'))
      .mockResolvedValueOnce(json(200, { ok: true }));
    const client = createHttpClient({ fetch, auth: hooks });

    await expect(client.get('/api/v1/users/me')).resolves.toEqual({ ok: true });
    expect(hooks.refresh).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledTimes(2);
    const retryHeaders = (fetch.mock.calls[1] as unknown as [string, RequestInit])[1].headers as Record<string, string>;
    expect(retryHeaders.Authorization).toBe('Bearer new-token');
    expect(hooks.onAuthFailure).not.toHaveBeenCalled();
  });

  it('logs out when the refresh fails', async () => {
    const hooks = authHooks({ refresh: vi.fn(async () => false) });
    const fetch = vi.fn(async () => json(401, { status: 401, detail: 'Token expired' }, 'application/problem+json'));
    const client = createHttpClient({ fetch, auth: hooks });

    const error = (await client.get('/api/v1/users/me').catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(401);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(hooks.onAuthFailure).toHaveBeenCalledTimes(1);
  });

  it('does not loop when the retried request is still unauthorized', async () => {
    const hooks = authHooks();
    const fetch = vi.fn(async () => json(401, { status: 401 }, 'application/problem+json'));
    const client = createHttpClient({ fetch, auth: hooks });
    await expect(client.get('/api/v1/users/me')).rejects.toBeInstanceOf(ApiError);
    expect(hooks.refresh).toHaveBeenCalledTimes(1);
    expect(fetch).toHaveBeenCalledTimes(2);
    expect(hooks.onAuthFailure).toHaveBeenCalledTimes(1);
  });

  it('never refreshes for public endpoints (e.g. a failed login)', async () => {
    const hooks = authHooks();
    const fetch = vi.fn(async () => json(401, { status: 401, code: 'invalid_credentials', detail: 'Invalid email or password.' }, 'application/problem+json'));
    const client = createHttpClient({ fetch, auth: hooks });
    const error = (await client.post('/api/v1/auth/login', {}, { auth: false }).catch((e: unknown) => e)) as ApiError;
    expect(error.code).toBe('invalid_credentials');
    expect(error.detail).toBe('Invalid email or password.');
    expect(hooks.refresh).not.toHaveBeenCalled();
    expect(hooks.onAuthFailure).not.toHaveBeenCalled();
  });

  it('turns problem+json errors into ApiError and network failures into status 0', async () => {
    const client = createHttpClient({
      fetch: vi.fn(async () => json(422, { status: 422, code: 'habit_archived', detail: 'Habit is archived.' }, 'application/problem+json')),
      auth: authHooks(),
    });
    await expect(client.post('/api/v1/activities', {})).rejects.toMatchObject({ status: 422, code: 'habit_archived', detail: 'Habit is archived.' });

    const offline = createHttpClient({ fetch: vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))), auth: authHooks() });
    await expect(offline.get('/api/v1/habits')).rejects.toMatchObject({ status: 0, code: 'network_error' });
  });

  it('propagates aborts untouched', async () => {
    const abort = new DOMException('aborted', 'AbortError');
    const client = createHttpClient({ fetch: vi.fn(async () => Promise.reject(abort)), auth: authHooks() });
    await expect(client.get('/api/v1/habits')).rejects.toBe(abort);
  });
});
