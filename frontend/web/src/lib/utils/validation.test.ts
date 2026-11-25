import { describe, expect, it } from 'vitest';
import { validateBadgeRule, validateChallenge, validateHabit, validateLogin, validatePassword, validatePasswordChange } from './validation';

const habit = {
  title: 'Morning run',
  description: '',
  category: 'fitness',
  frequency: 'daily',
  target_per_period: 1,
  visibility: 'private',
  color: '#4F46E5',
};

describe('habit validation (contract rules)', () => {
  it('accepts a valid habit', () => {
    expect(validateHabit(habit)).toEqual({});
  });

  it('enforces title 3–80 and description ≤ 500', () => {
    expect(validateHabit({ ...habit, title: 'ab' }).title).toBeDefined();
    expect(validateHabit({ ...habit, title: 'x'.repeat(81) }).title).toBeDefined();
    expect(validateHabit({ ...habit, title: '   ab   ' }).title).toBeDefined();
    expect(validateHabit({ ...habit, description: 'x'.repeat(501) }).description).toBeDefined();
  });

  it('enforces daily ⇒ 1 and weekly ⇒ 1..7', () => {
    expect(validateHabit({ ...habit, target_per_period: 2 }).target_per_period).toBeDefined();
    expect(validateHabit({ ...habit, frequency: 'weekly', target_per_period: 3 })).toEqual({});
    expect(validateHabit({ ...habit, frequency: 'weekly', target_per_period: 8 }).target_per_period).toBeDefined();
    expect(validateHabit({ ...habit, frequency: 'weekly', target_per_period: 0 }).target_per_period).toBeDefined();
  });

  it('rejects unknown enums and bad colours', () => {
    const errors = validateHabit({ ...habit, category: 'gaming', visibility: 'public', color: 'blue' });
    expect(Object.keys(errors).sort()).toEqual(['category', 'color', 'visibility']);
  });
});

describe('password policy', () => {
  it('requires ≥ 8 chars with upper, lower and digit', () => {
    expect(validatePassword('TeamPulse@2026')).toBeNull();
    expect(validatePassword('Short1')).toMatch(/8 characters/);
    expect(validatePassword('alllowercase1')).toMatch(/upper-case/);
    expect(validatePassword('ALLUPPERCASE1')).toMatch(/lower-case/);
    expect(validatePassword('NoDigitsHere')).toMatch(/digit/);
  });

  it('validates password changes', () => {
    expect(validatePasswordChange({ current: 'Old@Pass1', next: 'New@Pass1', confirm: 'New@Pass1' })).toEqual({});
    expect(validatePasswordChange({ current: '', next: 'New@Pass1', confirm: 'x' })).toEqual({
      current: expect.any(String),
      confirm: 'Passwords do not match.',
    });
    expect(validatePasswordChange({ current: 'Same@Pass1', next: 'Same@Pass1', confirm: 'Same@Pass1' }).next).toBeDefined();
  });
});

describe('other forms', () => {
  it('validates login', () => {
    expect(validateLogin({ email: 'alice.johnson@teampulse.io', password: 'x' })).toEqual({});
    expect(validateLogin({ email: 'nope', password: '' })).toEqual({ email: expect.any(String), password: expect.any(String) });
  });

  it('validates challenges', () => {
    const base = { title: 'November Step-Up', description: '', starts_on: '2026-11-01', ends_on: '2026-11-30', target_count: 20 };
    expect(validateChallenge(base)).toEqual({});
    expect(validateChallenge({ ...base, ends_on: '2026-10-31' }).ends_on).toMatch(/on or after/);
    expect(validateChallenge({ ...base, target_count: 0 }).target_count).toBeDefined();
    expect(validateChallenge({ ...base, starts_on: '' }).starts_on).toBeDefined();
  });

  it('validates badge rules', () => {
    const rule = { code: 'week_warrior', name: 'Week Warrior', description: '', icon: '🔥', criterion: 'streak_days', category: '', threshold: 7 };
    expect(validateBadgeRule(rule)).toEqual({});
    expect(validateBadgeRule({ ...rule, code: 'Bad Code' }).code).toBeDefined();
    expect(validateBadgeRule({ ...rule, criterion: 'category_completions' }).category).toBeDefined();
    expect(validateBadgeRule({ ...rule, criterion: 'category_completions', category: 'sleep' })).toEqual({});
  });
});
