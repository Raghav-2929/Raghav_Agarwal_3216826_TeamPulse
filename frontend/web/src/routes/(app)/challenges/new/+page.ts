import { requireRole } from '$lib/guards';
import type { PageLoad } from './$types';

/** Only managers (own team or org-wide) and admins may create challenges. */
export const load: PageLoad = async ({ parent }) => {
  await parent();
  requireRole(['manager', 'admin'], 'Only managers and administrators can create challenges.');
  return {};
};
