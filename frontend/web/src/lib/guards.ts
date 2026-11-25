/**
 * Route guards used by `+layout.ts` / `+page.ts` load functions.
 *  - `requireSession` → redirects to /login (preserving the target) when there is no session.
 *  - `requireRole`    → throws a 403 that renders the in-shell error page.
 */
import { error, redirect } from '@sveltejs/kit';
import type { Role } from '$lib/api/types';
import { session } from '$lib/state/session.svelte';
import { canAccess } from '$lib/utils/nav';

export async function requireSession(url: URL): Promise<void> {
  if (await session.ensure()) return;
  const target = `${url.pathname}${url.search}`;
  redirect(307, `/login?redirect=${encodeURIComponent(target)}`);
}

export function requireRole(roles: Role[], message = 'You do not have permission to view this page.'): void {
  if (!session.hasRole(...roles)) error(403, { message, code: 'forbidden', status: 403 });
}

/** Checks the central ROUTE_ACCESS table for a pathname. */
export function requireRouteAccess(pathname: string, message?: string): void {
  if (!canAccess(pathname, session.role)) error(403, { message: message ?? 'Your role does not have access to this page.', code: 'forbidden', status: 403 });
}
