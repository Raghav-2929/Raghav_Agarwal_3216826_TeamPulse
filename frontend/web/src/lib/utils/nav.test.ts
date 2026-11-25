import { describe, expect, it } from 'vitest';
import { activeHref, canAccess, navForRole, safeRedirect } from './nav';

const hrefs = (role: Parameters<typeof navForRole>[0]) => navForRole(role).flatMap((s) => s.items.map((i) => i.href));

describe('role-based navigation', () => {
  it('shows employees only personal, team-habit and account links', () => {
    const links = hrefs('employee');
    expect(links).toEqual(['/dashboard', '/habits', '/challenges', '/analytics', '/habits/team', '/notifications', '/profile']);
    expect(links).not.toContain('/team');
    expect(links.some((h) => h.startsWith('/admin'))).toBe(false);
  });

  it('adds team insights for managers but no admin area', () => {
    const links = hrefs('manager');
    expect(links).toContain('/team');
    expect(links.some((h) => h.startsWith('/admin'))).toBe(false);
  });

  it('gives admins every section', () => {
    const sections = navForRole('admin').map((s) => s.id);
    expect(sections).toEqual(['personal', 'team', 'admin', 'account']);
    expect(hrefs('admin')).toEqual(expect.arrayContaining(['/team', '/admin/users', '/admin/teams', '/admin/badge-rules', '/admin/insights']));
  });

  it('returns nothing without a role', () => {
    expect(navForRole(null)).toEqual([]);
  });
});

describe('route access', () => {
  it('protects admin routes', () => {
    expect(canAccess('/admin/users', 'employee')).toBe(false);
    expect(canAccess('/admin/users', 'manager')).toBe(false);
    expect(canAccess('/admin/users', 'admin')).toBe(true);
    expect(canAccess('/admin', 'admin')).toBe(true);
  });

  it('protects team insights and challenge creation', () => {
    expect(canAccess('/team', 'employee')).toBe(false);
    expect(canAccess('/team', 'manager')).toBe(true);
    expect(canAccess('/challenges/new', 'employee')).toBe(false);
    expect(canAccess('/challenges/new', 'manager')).toBe(true);
  });

  it('does not confuse similar prefixes', () => {
    expect(canAccess('/teams-overview', 'employee')).toBe(true);
    expect(canAccess('/habits/team', 'employee')).toBe(true);
    expect(canAccess('/challenges/123', 'employee')).toBe(true);
  });

  it('denies everything without a role', () => {
    expect(canAccess('/dashboard', null)).toBe(false);
  });
});

describe('active link + redirects', () => {
  it('picks the longest matching nav prefix', () => {
    expect(activeHref('/habits/team')).toBe('/habits/team');
    expect(activeHref('/habits/abc/edit')).toBe('/habits');
    expect(activeHref('/admin/users')).toBe('/admin/users');
    expect(activeHref('/unknown')).toBeNull();
  });

  it('only allows same-origin redirect targets', () => {
    expect(safeRedirect('/challenges?status=active')).toBe('/challenges?status=active');
    expect(safeRedirect('https://evil.example')).toBe('/dashboard');
    expect(safeRedirect('//evil.example')).toBe('/dashboard');
    expect(safeRedirect('/\\evil.example')).toBe('/dashboard');
    expect(safeRedirect('/login?redirect=/x')).toBe('/dashboard');
    expect(safeRedirect(null)).toBe('/dashboard');
  });
});
