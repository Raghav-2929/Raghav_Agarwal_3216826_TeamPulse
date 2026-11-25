/**
 * Client-side validation mirroring the REST contract rules. Each validator returns a map of
 * `field → message`; an empty object means valid. Server-side validation remains authoritative.
 */
import { BADGE_CRITERIA, CATEGORIES, FREQUENCIES, ROLES, VISIBILITIES } from '$lib/api/types';
import { diffDays, isValidISODate } from './dates';

export type FieldErrors = Record<string, string>;

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const HEX_COLOR = /^#[0-9a-fA-F]{6}$/;

export function hasErrors(errors: FieldErrors): boolean {
  return Object.keys(errors).length > 0;
}

export function validateEmail(email: string): string | null {
  if (!email.trim()) return 'Email is required.';
  if (!EMAIL.test(email.trim())) return 'Enter a valid email address.';
  return null;
}

/** Password policy: at least 8 characters with upper-case, lower-case and a digit. */
export function validatePassword(password: string): string | null {
  if (!password) return 'Password is required.';
  if (password.length < 8) return 'Use at least 8 characters.';
  if (!/[A-Z]/.test(password)) return 'Include an upper-case letter.';
  if (!/[a-z]/.test(password)) return 'Include a lower-case letter.';
  if (!/\d/.test(password)) return 'Include a digit.';
  return null;
}

export function validateLogin(form: { email: string; password: string }): FieldErrors {
  const errors: FieldErrors = {};
  const email = validateEmail(form.email);
  if (email) errors.email = email;
  if (!form.password) errors.password = 'Password is required.';
  return errors;
}

export interface HabitFormValues {
  title: string;
  description: string;
  category: string;
  frequency: string;
  target_per_period: number;
  visibility: string;
  color: string;
}

export function validateHabit(form: HabitFormValues): FieldErrors {
  const errors: FieldErrors = {};
  const title = form.title.trim();
  if (title.length < 3) errors.title = 'Title must be at least 3 characters.';
  else if (title.length > 80) errors.title = 'Title must be at most 80 characters.';
  if (form.description.length > 500) errors.description = 'Description must be at most 500 characters.';
  if (!(CATEGORIES as readonly string[]).includes(form.category)) errors.category = 'Choose an activity type.';
  if (!(FREQUENCIES as readonly string[]).includes(form.frequency)) errors.frequency = 'Choose a frequency.';
  if (!(VISIBILITIES as readonly string[]).includes(form.visibility)) errors.visibility = 'Choose who can see this habit.';
  const target = Number(form.target_per_period);
  if (form.frequency === 'daily' && target !== 1) errors.target_per_period = 'Daily habits have a target of 1 per day.';
  if (form.frequency === 'weekly' && (!Number.isInteger(target) || target < 1 || target > 7))
    errors.target_per_period = 'Weekly target must be between 1 and 7.';
  if (form.color && !HEX_COLOR.test(form.color)) errors.color = 'Use a hex colour like #4F46E5.';
  return errors;
}

export function validateActivityNote(note: string): string | null {
  return note.length > 280 ? 'Notes are limited to 280 characters.' : null;
}

export interface ChallengeFormValues {
  title: string;
  description: string;
  starts_on: string;
  ends_on: string;
  target_count: number;
}

export function validateChallenge(form: ChallengeFormValues): FieldErrors {
  const errors: FieldErrors = {};
  const title = form.title.trim();
  if (title.length < 3) errors.title = 'Title must be at least 3 characters.';
  else if (title.length > 120) errors.title = 'Title must be at most 120 characters.';
  if (form.description.length > 1000) errors.description = 'Description must be at most 1000 characters.';
  if (!isValidISODate(form.starts_on)) errors.starts_on = 'Choose a start date.';
  if (!isValidISODate(form.ends_on)) errors.ends_on = 'Choose an end date.';
  if (!errors.starts_on && !errors.ends_on && diffDays(form.starts_on, form.ends_on) < 0)
    errors.ends_on = 'The end date must be on or after the start date.';
  const target = Number(form.target_count);
  if (!Number.isInteger(target) || target < 1) errors.target_count = 'Target must be a whole number of at least 1.';
  else if (target > 1000) errors.target_count = 'Target must be at most 1000.';
  return errors;
}

export interface UserFormValues {
  email: string;
  full_name: string;
  password: string;
  role: string;
}

export function validateNewUser(form: UserFormValues): FieldErrors {
  const errors: FieldErrors = {};
  const email = validateEmail(form.email);
  if (email) errors.email = email;
  const name = validateFullName(form.full_name);
  if (name) errors.full_name = name;
  const password = validatePassword(form.password);
  if (password) errors.password = password;
  if (!(ROLES as readonly string[]).includes(form.role)) errors.role = 'Choose a role.';
  return errors;
}

export function validateFullName(name: string): string | null {
  const trimmed = name.trim();
  if (trimmed.length < 2) return 'Name must be at least 2 characters.';
  if (trimmed.length > 120) return 'Name must be at most 120 characters.';
  return null;
}

export function validatePasswordChange(form: { current: string; next: string; confirm: string }): FieldErrors {
  const errors: FieldErrors = {};
  if (!form.current) errors.current = 'Enter your current password.';
  const policy = validatePassword(form.next);
  if (policy) errors.next = policy;
  else if (form.next === form.current) errors.next = 'Choose a password different from the current one.';
  if (form.confirm !== form.next) errors.confirm = 'Passwords do not match.';
  return errors;
}

export interface BadgeRuleFormValues {
  code: string;
  name: string;
  description: string;
  icon: string;
  criterion: string;
  category: string;
  threshold: number;
}

export function validateBadgeRule(form: BadgeRuleFormValues): FieldErrors {
  const errors: FieldErrors = {};
  if (!/^[a-z0-9_]{3,40}$/.test(form.code)) errors.code = 'Use 3–40 lower-case letters, digits or underscores.';
  if (form.name.trim().length < 2) errors.name = 'Name is required.';
  if (!form.icon.trim()) errors.icon = 'Pick an icon (emoji).';
  if (!(BADGE_CRITERIA as readonly string[]).includes(form.criterion)) errors.criterion = 'Choose a criterion.';
  if (form.criterion === 'category_completions' && !(CATEGORIES as readonly string[]).includes(form.category))
    errors.category = 'Category completions need a category.';
  const threshold = Number(form.threshold);
  if (!Number.isInteger(threshold) || threshold < 1) errors.threshold = 'Threshold must be a whole number of at least 1.';
  return errors;
}

export function validateTeam(form: { name: string; description: string }): FieldErrors {
  const errors: FieldErrors = {};
  if (form.name.trim().length < 2) errors.name = 'Team name must be at least 2 characters.';
  else if (form.name.trim().length > 80) errors.name = 'Team name must be at most 80 characters.';
  if (form.description.length > 500) errors.description = 'Description must be at most 500 characters.';
  return errors;
}

export function validateReminderHour(hour: number): string | null {
  return Number.isInteger(hour) && hour >= 0 && hour <= 23 ? null : 'Pick an hour between 0 and 23.';
}
