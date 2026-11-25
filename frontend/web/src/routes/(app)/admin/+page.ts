import { redirect } from '@sveltejs/kit';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ parent }) => {
  await parent(); // admin guard runs first, so non-admins get the 403 page rather than a redirect
  redirect(307, '/admin/users');
};
