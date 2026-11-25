import { env } from '$env/dynamic/public';
import { createApi } from './endpoints';
import { createHttpClient } from './http';

/**
 * Base URL for API calls. Empty by default: in production CloudFront serves `/api/*` from the
 * gateway on the same origin, and in development the Vite proxy forwards `/api` to the gateway.
 */
export const API_BASE_URL = (env.PUBLIC_API_BASE_URL ?? '').trim();

/** Shared HTTP client; the session store installs its auth hooks on start-up. */
export const http = createHttpClient({ baseUrl: API_BASE_URL });

/** Typed TeamPulse API. */
export const api = createApi(http);

export * from './types';
export { ApiError, errorMessage, isApiError } from './errors';
