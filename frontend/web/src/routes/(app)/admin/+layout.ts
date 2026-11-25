import { requireRole } from '$lib/guards';
import type { LayoutLoad } from './$types';

/** Everything under /admin is restricted to administrators (403 page otherwise). */
export const load: LayoutLoad = async ({ parent }) => {
  await parent();
  requireRole(['admin'], 'The administration area is restricted to administrators.');
  return {};
};
