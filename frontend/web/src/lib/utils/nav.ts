import type { Role } from '$lib/api/types';

export type NavSectionId = 'personal' | 'team' | 'admin' | 'account';

export interface NavItem {
  href: string;
  label: string;
  icon: string;
  roles: readonly Role[];
  section: NavSectionId;
}

export interface NavSection {
  id: NavSectionId;
  label: string;
  items: NavItem[];
}

const ALL: readonly Role[] = ['employee', 'manager', 'admin'];
const LEADS: readonly Role[] = ['manager', 'admin'];
const ADMIN: readonly Role[] = ['admin'];

/** Single source of truth for the sidebar, mapping each route to the roles that may see it. */
export const NAV_ITEMS: readonly NavItem[] = [
  { href: '/dashboard', label: 'Dashboard', icon: '🏠', roles: ALL, section: 'personal' },
  { href: '/habits', label: 'My habits', icon: '✅', roles: ALL, section: 'personal' },
  { href: '/challenges', label: 'Challenges', icon: '🏆', roles: ALL, section: 'personal' },
  { href: '/analytics', label: 'My insights', icon: '📈', roles: ALL, section: 'personal' },
  { href: '/habits/team', label: 'Team habits', icon: '🤝', roles: ALL, section: 'team' },
  { href: '/team', label: 'Team insights', icon: '👥', roles: LEADS, section: 'team' },
  { href: '/admin/users', label: 'Users', icon: '🧑‍💼', roles: ADMIN, section: 'admin' },
  { href: '/admin/teams', label: 'Teams', icon: '🏢', roles: ADMIN, section: 'admin' },
  { href: '/admin/badge-rules', label: 'Badge rules', icon: '🎖️', roles: ADMIN, section: 'admin' },
  { href: '/admin/insights', label: 'Org insights', icon: '🌐', roles: ADMIN, section: 'admin' },
  { href: '/notifications', label: 'Notifications', icon: '🔔', roles: ALL, section: 'account' },
  { href: '/profile', label: 'Profile', icon: '👤', roles: ALL, section: 'account' },
];

const SECTION_LABELS: Record<NavSectionId, string> = {
  personal: 'Personal',
  team: 'Team',
  admin: 'Administration',
  account: 'Account',
};

const SECTION_ORDER: NavSectionId[] = ['personal', 'team', 'admin', 'account'];

/** Navigation visible to a role, grouped into non-empty sections. */
export function navForRole(role: Role | null | undefined, items: readonly NavItem[] = NAV_ITEMS): NavSection[] {
  if (!role) return [];
  return SECTION_ORDER.map((id) => ({
    id,
    label: SECTION_LABELS[id],
    items: items.filter((item) => item.section === id && item.roles.includes(role)),
  })).filter((section) => section.items.length > 0);
}

/** Routes that require specific roles (checked by layout load guards). Longest prefix wins. */
export const ROUTE_ACCESS: readonly { prefix: string; roles: readonly Role[] }[] = [
  { prefix: '/admin', roles: ADMIN },
  { prefix: '/team', roles: LEADS },
  { prefix: '/challenges/new', roles: LEADS },
];

function matchesPrefix(pathname: string, prefix: string): boolean {
  return pathname === prefix || pathname.startsWith(`${prefix}/`);
}

/** Whether `role` may open `pathname`. Unlisted routes are open to every signed-in role. */
export function canAccess(pathname: string, role: Role | null | undefined): boolean {
  if (!role) return false;
  const rule = [...ROUTE_ACCESS].sort((a, b) => b.prefix.length - a.prefix.length).find((r) => matchesPrefix(pathname, r.prefix));
  return rule ? rule.roles.includes(role) : true;
}

/**
 * The nav href that should be highlighted for `pathname`: the longest matching prefix, so
 * `/habits/team` highlights "Team habits" while `/habits/123` highlights "My habits".
 */
export function activeHref(pathname: string, items: readonly NavItem[] = NAV_ITEMS): string | null {
  let best: string | null = null;
  for (const item of items) {
    if (matchesPrefix(pathname, item.href) && (!best || item.href.length > best.length)) best = item.href;
  }
  return best;
}

/** Only allow same-origin absolute paths as post-login redirect targets. */
export function safeRedirect(target: string | null | undefined, fallback = '/dashboard'): string {
  if (!target || !target.startsWith('/') || target.startsWith('//') || target.startsWith('/\\')) return fallback;
  if (target === '/login' || target.startsWith('/login?') || target.startsWith('/login/')) return fallback;
  return target;
}

export const ROLE_LABELS: Record<Role, string> = {
  employee: 'Employee',
  manager: 'Manager',
  admin: 'Admin',
};
