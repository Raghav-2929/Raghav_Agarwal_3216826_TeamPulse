import { redirect } from '@sveltejs/kit';
import { session } from '$lib/state/session.svelte';
import { safeRedirect } from '$lib/utils/nav';
import type { PageLoad } from './$types';

/** Already signed in (or restorable from the refresh token)? Skip the form. */
export const load: PageLoad = async ({ url }) => {
  if (await session.ensure()) redirect(307, safeRedirect(url.searchParams.get('redirect')));
  return {};
};
