import type { ProblemDetails, ProblemFieldError } from './types';

/**
 * Typed error for every non-2xx API response (RFC 7807 problem+json) and for network failures.
 * `message` is always safe to show to users (it is the problem `detail` when present).
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly title: string;
  readonly detail: string;
  readonly requestId?: string;
  readonly type?: string;
  readonly instance?: string;
  /** Field-level validation messages keyed by field name (from `errors`). */
  readonly fieldErrors: Record<string, string>;

  constructor(init: {
    status: number;
    code?: string;
    title?: string;
    detail?: string;
    requestId?: string;
    type?: string;
    instance?: string;
    fieldErrors?: Record<string, string>;
  }) {
    const detail = init.detail || init.title || defaultMessage(init.status);
    super(detail);
    this.name = 'ApiError';
    this.status = init.status;
    this.code = init.code || defaultCode(init.status);
    this.title = init.title || defaultTitle(init.status);
    this.detail = detail;
    this.requestId = init.requestId;
    this.type = init.type;
    this.instance = init.instance;
    this.fieldErrors = init.fieldErrors ?? {};
  }

  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

export function isApiError(value: unknown): value is ApiError {
  return value instanceof ApiError;
}

/** Converts the `errors` member of a problem document into `{field: message}`. */
export function toFieldErrors(errors: ProblemDetails['errors']): Record<string, string> {
  const out: Record<string, string> = {};
  if (!errors) return out;
  if (Array.isArray(errors)) {
    for (const e of errors as ProblemFieldError[]) {
      if (!e || typeof e !== 'object') continue;
      const loc = Array.isArray(e.loc) ? e.loc.filter((p) => p !== 'body' && p !== 'query' && p !== 'path') : [];
      const field = e.field ?? (loc.length ? String(loc[loc.length - 1]) : '');
      const msg = e.msg ?? e.message ?? '';
      if (field && msg && !out[field]) out[field] = msg;
    }
    return out;
  }
  if (typeof errors === 'object') {
    for (const [field, value] of Object.entries(errors)) {
      if (typeof value === 'string') out[field] = value;
      else if (Array.isArray(value) && typeof value[0] === 'string') out[field] = value[0];
    }
  }
  return out;
}

/** Builds an ApiError from a parsed body (problem document or anything else) and HTTP status. */
export function problemToError(status: number, body: unknown, requestId?: string): ApiError {
  if (body && typeof body === 'object') {
    const p = body as ProblemDetails & { message?: unknown };
    // FastAPI default `{"detail": "..."}` or `{"detail": [...]}` is tolerated too.
    const detail = typeof p.detail === 'string' ? p.detail : typeof p.message === 'string' ? p.message : undefined;
    const errors = p.errors ?? (Array.isArray(p.detail) ? (p.detail as unknown as ProblemFieldError[]) : undefined);
    return new ApiError({
      status: typeof p.status === 'number' ? p.status : status,
      code: typeof p.code === 'string' ? p.code : undefined,
      title: typeof p.title === 'string' ? p.title : undefined,
      detail: detail ?? (Array.isArray(p.detail) ? 'Some fields are invalid.' : undefined),
      requestId: typeof p.request_id === 'string' ? p.request_id : requestId,
      type: typeof p.type === 'string' ? p.type : undefined,
      instance: typeof p.instance === 'string' ? p.instance : undefined,
      fieldErrors: toFieldErrors(errors),
    });
  }
  if (typeof body === 'string' && body.trim() && body.length < 300) {
    return new ApiError({ status, detail: body.trim(), requestId });
  }
  return new ApiError({ status, requestId });
}

/** Reads a non-OK fetch Response into an ApiError (never throws). */
export async function parseErrorResponse(response: Response): Promise<ApiError> {
  const requestId = response.headers.get('x-request-id') ?? undefined;
  let body: unknown = null;
  try {
    const text = await response.text();
    if (text) {
      const contentType = response.headers.get('content-type') ?? '';
      body = contentType.includes('json') || /^[[{]/.test(text.trim()) ? JSON.parse(text) : text;
    }
  } catch {
    body = null;
  }
  return problemToError(response.status, body, requestId);
}

/** User-facing message for any thrown value. */
export function errorMessage(error: unknown, fallback = 'Something went wrong. Please try again.'): string {
  if (isApiError(error)) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function defaultCode(status: number): string {
  switch (status) {
    case 0:
      return 'network_error';
    case 400:
      return 'bad_request';
    case 401:
      return 'unauthorized';
    case 403:
      return 'forbidden';
    case 404:
      return 'not_found';
    case 409:
      return 'conflict';
    case 422:
      return 'validation_error';
    case 423:
      return 'locked';
    case 429:
      return 'rate_limited';
    case 503:
      return 'dependency_unavailable';
    default:
      return status >= 500 ? 'server_error' : 'error';
  }
}

function defaultTitle(status: number): string {
  if (status === 0) return 'Network error';
  if (status === 401) return 'Unauthorized';
  if (status === 403) return 'Forbidden';
  if (status === 404) return 'Not found';
  if (status === 409) return 'Conflict';
  if (status === 422) return 'Validation error';
  if (status >= 500) return 'Server error';
  return 'Request failed';
}

function defaultMessage(status: number): string {
  if (status === 0) return 'Cannot reach the TeamPulse service. Check your connection and try again.';
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'You do not have permission to do that.';
  if (status === 404) return 'The requested item was not found.';
  if (status === 409) return 'This conflicts with the current state. Refresh and try again.';
  if (status === 422) return 'Some fields are invalid.';
  if (status === 429) return 'Too many requests. Please slow down.';
  if (status === 503) return 'A dependent service is temporarily unavailable. Please try again shortly.';
  if (status >= 500) return 'The server encountered an error. Please try again.';
  return 'The request failed.';
}
