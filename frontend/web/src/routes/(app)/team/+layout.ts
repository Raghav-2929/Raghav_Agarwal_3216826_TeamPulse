import { requireRole } from '$lib/guards';
import type { LayoutLoad } from './$types';

/** Aggregated team insights: managers (for the teams they manage) and admins only. */
export const load: LayoutLoad = async ({ parent }) => {
  await parent();
  requireRole(['manager', 'admin'], 'Team insights are available to managers and administrators only.');
  return {};
};
