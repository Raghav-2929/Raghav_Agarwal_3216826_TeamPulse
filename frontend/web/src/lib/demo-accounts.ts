import type { Role } from '$lib/api/types';

/** Seeded demo users (local/dev environments). Every account uses the same demo password. */
export const DEMO_PASSWORD = 'TeamPulse@2026';

export interface DemoAccount {
  email: string;
  name: string;
  role: Role;
  team: string | null;
}

export const DEMO_ACCOUNTS: readonly DemoAccount[] = [
  { email: 'admin@teampulse.io', name: 'Admin', role: 'admin', team: null },
  { email: 'maya.patel@teampulse.io', name: 'Maya Patel', role: 'manager', team: 'Engineering' },
  { email: 'omar.haddad@teampulse.io', name: 'Omar Haddad', role: 'manager', team: 'Marketing' },
  { email: 'priya.nair@teampulse.io', name: 'Priya Nair', role: 'manager', team: 'Operations' },
  { email: 'alice.johnson@teampulse.io', name: 'Alice Johnson', role: 'employee', team: 'Engineering' },
  { email: 'ben.carter@teampulse.io', name: 'Ben Carter', role: 'employee', team: 'Engineering' },
  { email: 'chloe.kim@teampulse.io', name: 'Chloe Kim', role: 'employee', team: 'Engineering' },
  { email: 'dev.sharma@teampulse.io', name: 'Dev Sharma', role: 'employee', team: 'Engineering' },
  { email: 'emma.davis@teampulse.io', name: 'Emma Davis', role: 'employee', team: 'Marketing' },
  { email: 'felix.wong@teampulse.io', name: 'Felix Wong', role: 'employee', team: 'Marketing' },
  { email: 'grace.lee@teampulse.io', name: 'Grace Lee', role: 'employee', team: 'Marketing' },
  { email: 'henry.lopez@teampulse.io', name: 'Henry Lopez', role: 'employee', team: 'Operations' },
  { email: 'isla.brown@teampulse.io', name: 'Isla Brown', role: 'employee', team: 'Operations' },
  { email: 'jack.wilson@teampulse.io', name: 'Jack Wilson', role: 'employee', team: 'Operations' },
];
