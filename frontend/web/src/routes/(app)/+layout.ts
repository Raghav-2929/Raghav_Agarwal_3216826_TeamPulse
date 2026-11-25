import { requireSession } from '$lib/guards';
import type { LayoutLoad } from './$types';

/** Every route in the (app) group needs a signed-in user (restored from the refresh token on reload). */
export const load: LayoutLoad = async ({ url }) => {
  await requireSession(url);
  return {};
};
