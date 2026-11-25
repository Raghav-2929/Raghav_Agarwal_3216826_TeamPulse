import { CATEGORIES, type Category } from '$lib/api/types';

export interface CategoryMeta {
  value: Category;
  label: string;
  icon: string;
  /** Design token holding the category colour. */
  color: string;
}

const ICONS: Record<Category, string> = {
  fitness: '🏃',
  mindfulness: '🧘',
  nutrition: '🥗',
  sleep: '😴',
  hydration: '💧',
  learning: '📚',
};

export const CATEGORY_META: Record<Category, CategoryMeta> = Object.fromEntries(
  CATEGORIES.map((value) => [
    value,
    {
      value,
      label: value.charAt(0).toUpperCase() + value.slice(1),
      icon: ICONS[value],
      color: `var(--tp-color-category-${value})`,
    },
  ]),
) as Record<Category, CategoryMeta>;

export const CATEGORY_OPTIONS: CategoryMeta[] = CATEGORIES.map((c) => CATEGORY_META[c]);

export function categoryLabel(value: string | null | undefined): string {
  return value && value in CATEGORY_META ? CATEGORY_META[value as Category].label : 'Any';
}

export function categoryIcon(value: string | null | undefined): string {
  return value && value in CATEGORY_META ? CATEGORY_META[value as Category].icon : '⭐';
}

export function categoryColor(value: string | null | undefined): string {
  return value && value in CATEGORY_META ? CATEGORY_META[value as Category].color : 'var(--tp-color-primary)';
}

export function capitalize(value: string): string {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

/** Next streak milestone above `current` (7, 14, 30, 60, 100, then +100). */
export function nextMilestone(current: number): number {
  const milestones = [7, 14, 30, 60, 100];
  for (const m of milestones) if (current < m) return m;
  return Math.floor(current / 100) * 100 + 100;
}
