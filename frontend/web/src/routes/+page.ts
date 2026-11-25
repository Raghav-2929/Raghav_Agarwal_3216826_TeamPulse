import { redirect } from '@sveltejs/kit';
import { session } from '$lib/state/session.svelte';
import type { PageLoad } from './$types';

/** `/` → dashboard when signed in (or restorable), otherwise the login page. */
export const load: PageLoad = async () => {
  redirect(307, (await session.ensure()) ? '/dashboard' : '/login');
};
