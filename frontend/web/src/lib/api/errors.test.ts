import { describe, expect, it } from 'vitest';
import { ApiError, errorMessage, parseErrorResponse, problemToError, toFieldErrors } from './errors';

function problemResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(typeof body === 'string' ? body : JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/problem+json', ...headers },
  });
}

describe('RFC 7807 problem parsing', () => {
  it('maps every problem member onto ApiError', async () => {
    const error = await parseErrorResponse(
      problemResponse(409, {
        type: 'https://teampulse.io/problems/already-logged',
        title: 'Conflict',
        status: 409,
        detail: 'This habit is already logged for 2026-11-08.',
        code: 'already_logged',
        instance: '/api/v1/activities',
        request_id: 'req-123',
      }),
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(409);
    expect(error.code).toBe('already_logged');
    expect(error.title).toBe('Conflict');
    expect(error.detail).toBe('This habit is already logged for 2026-11-08.');
    expect(error.message).toBe(error.detail);
    expect(error.requestId).toBe('req-123');
    expect(error.instance).toBe('/api/v1/activities');
  });

  it('falls back to the X-Request-ID header and status defaults', async () => {
    const error = await parseErrorResponse(problemResponse(503, '', { 'x-request-id': 'hdr-9' }));
    expect(error.status).toBe(503);
    expect(error.code).toBe('dependency_unavailable');
    expect(error.requestId).toBe('hdr-9');
    expect(error.detail).toMatch(/temporarily unavailable/);
  });

  it('extracts field errors from list and map formats', () => {
    expect(
      toFieldErrors([
        { loc: ['body', 'title'], msg: 'String should have at least 3 characters' },
        { field: 'target_per_period', message: 'must be 1 for daily habits' },
      ]),
    ).toEqual({ title: 'String should have at least 3 characters', target_per_period: 'must be 1 for daily habits' });
    expect(toFieldErrors({ email: ['already taken'], name: 'required' })).toEqual({ email: 'already taken', name: 'required' });
    expect(toFieldErrors(undefined)).toEqual({});
  });

  it('tolerates FastAPI-style `detail` arrays and plain text', () => {
    const fromList = problemToError(422, { detail: [{ loc: ['body', 'email'], msg: 'invalid email' }] });
    expect(fromList.code).toBe('validation_error');
    expect(fromList.fieldErrors).toEqual({ email: 'invalid email' });
    expect(fromList.detail).toBe('Some fields are invalid.');

    expect(problemToError(502, 'Bad gateway').detail).toBe('Bad gateway');
    expect(problemToError(500, null).detail).toMatch(/server encountered an error/);
  });

  it('produces user-facing messages for any thrown value', () => {
    expect(errorMessage(new ApiError({ status: 401, detail: 'Invalid email or password.' }))).toBe('Invalid email or password.');
    expect(errorMessage(new Error('boom'))).toBe('boom');
    expect(errorMessage('weird')).toMatch(/Something went wrong/);
    expect(new ApiError({ status: 0 }).isNetworkError).toBe(true);
  });
});
