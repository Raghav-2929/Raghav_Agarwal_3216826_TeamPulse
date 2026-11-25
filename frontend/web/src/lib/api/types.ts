/**
 * Types mirroring the TeamPulse REST contract v1 (docs/api-contract.md at the repository root).
 * Field names are snake_case exactly as on the wire.
 */

export type UUID = string;
/** `YYYY-MM-DD` */
export type ISODate = string;
/** ISO-8601 UTC timestamp */
export type ISODateTime = string;

export type Role = 'employee' | 'manager' | 'admin';
export const ROLES: readonly Role[] = ['employee', 'manager', 'admin'] as const;

export type Category = 'fitness' | 'mindfulness' | 'nutrition' | 'sleep' | 'hydration' | 'learning';
export const CATEGORIES: readonly Category[] = ['fitness', 'mindfulness', 'nutrition', 'sleep', 'hydration', 'learning'] as const;

export type Frequency = 'daily' | 'weekly';
export const FREQUENCIES: readonly Frequency[] = ['daily', 'weekly'] as const;

export type Visibility = 'private' | 'team';
export const VISIBILITIES: readonly Visibility[] = ['private', 'team'] as const;

export type ChallengeStatus = 'upcoming' | 'active' | 'completed';
export const CHALLENGE_STATUSES: readonly ChallengeStatus[] = ['upcoming', 'active', 'completed'] as const;

export type BadgeCriterion = 'streak_days' | 'total_completions' | 'category_completions';
export const BADGE_CRITERIA: readonly BadgeCriterion[] = ['streak_days', 'total_completions', 'category_completions'] as const;

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
}

export interface PageQuery {
  page?: number;
  size?: number;
}

// ---------------------------------------------------------------- identity

export interface UserOut {
  id: UUID;
  email: string;
  full_name: string;
  role: Role;
  team_id: UUID | null;
  team_name: string | null;
  is_active: boolean;
  created_at: ISODateTime;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: 'bearer';
  expires_in: number;
  user: UserOut;
}

/** Claims carried by the RS256 access token. */
export interface AccessTokenClaims {
  sub: UUID;
  name: string;
  email: string;
  role: Role;
  team_id: UUID | null;
  team_name: string | null;
  managed_team_ids: UUID[];
  iss: string;
  aud: string;
  iat: number;
  exp: number;
  jti: string;
  typ: 'access';
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface UserCreate {
  email: string;
  full_name: string;
  password: string;
  role: Role;
  team_id?: UUID | null;
}

export interface UserUpdate {
  full_name?: string;
  role?: Role;
  team_id?: UUID | null;
  is_active?: boolean;
}

export interface UserListQuery extends PageQuery {
  role?: Role;
  team_id?: UUID;
  search?: string;
}

export interface PasswordChange {
  current_password: string;
  new_password: string;
}

export interface TeamOut {
  id: UUID;
  name: string;
  description: string | null;
  manager_id: UUID | null;
  manager_name: string | null;
  member_count: number;
}

export interface TeamCreate {
  name: string;
  description?: string | null;
  manager_id?: UUID | null;
}

export type TeamUpdate = Partial<TeamCreate>;

export interface TeamMember {
  id: UUID;
  full_name: string;
  role: Role;
}

// ---------------------------------------------------------------- habits

export interface HabitOut {
  id: UUID;
  owner_id: UUID;
  owner_name: string;
  team_id: UUID | null;
  title: string;
  description: string | null;
  category: Category;
  frequency: Frequency;
  target_per_period: number;
  visibility: Visibility;
  color: string | null;
  is_archived: boolean;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

export interface HabitCreate {
  title: string;
  description?: string | null;
  category: Category;
  frequency: Frequency;
  target_per_period: number;
  visibility: Visibility;
  color?: string | null;
}

export type HabitUpdate = Partial<HabitCreate> & { is_archived?: boolean };

export interface HabitListQuery extends PageQuery {
  category?: Category;
  visibility?: Visibility;
  include_archived?: boolean;
  search?: string;
}

export interface TeamHabitListQuery extends PageQuery {
  category?: Category;
  search?: string;
}

// ---------------------------------------------------------------- activities

export interface ActivityOut {
  id: UUID;
  habit_id: UUID;
  category: Category;
  value: number;
  note: string | null;
  completed_on: ISODate;
  occurred_at: ISODateTime;
  created_at: ISODateTime;
}

export interface ActivityCreate {
  habit_id: UUID;
  completed_on?: ISODate;
  value?: number;
  note?: string;
}

export interface ActivityListQuery extends PageQuery {
  habit_id?: UUID;
  category?: Category;
  from?: ISODate;
  to?: ISODate;
}

// ---------------------------------------------------------------- challenges

export interface ChallengeOut {
  id: UUID;
  title: string;
  description: string | null;
  category: Category | null;
  team_id: UUID | null;
  team_name: string | null;
  starts_on: ISODate;
  ends_on: ISODate;
  target_count: number;
  status: ChallengeStatus;
  created_by: UUID;
  created_at: ISODateTime;
  participant_count: number;
  joined: boolean;
  my_score: number | null;
  my_goal_reached: boolean | null;
  show_on_leaderboard: boolean | null;
}

export interface ChallengeCreate {
  title: string;
  description?: string | null;
  category?: Category | null;
  team_id?: UUID | null;
  starts_on: ISODate;
  ends_on: ISODate;
  target_count: number;
}

export interface ChallengeUpdate {
  title?: string;
  description?: string | null;
  ends_on?: ISODate;
  target_count?: number;
}

export interface ChallengeListQuery extends PageQuery {
  status?: ChallengeStatus;
  category?: Category;
  search?: string;
  joined?: boolean;
  from?: ISODate;
  to?: ISODate;
}

export interface LeaderboardIndividual {
  rank: number;
  display_name: string;
  team_name: string | null;
  score: number;
  goal_reached: boolean;
  is_me: boolean;
}

export interface LeaderboardTeam {
  rank: number;
  team_id: UUID;
  team_name: string;
  participants: number;
  total_score: number;
  average_score: number;
}

export interface LeaderboardOut {
  challenge_id: UUID;
  my_rank: number | null;
  individuals: LeaderboardIndividual[];
  teams: LeaderboardTeam[];
}

export interface BadgeRuleOut {
  code: string;
  name: string;
  description: string;
  icon: string;
  criterion: BadgeCriterion;
  category: Category | null;
  threshold: number;
  is_active: boolean;
}

export type BadgeRuleUpsert = Omit<BadgeRuleOut, 'code'>;

// ---------------------------------------------------------------- insights

export interface Streak {
  habit_id: UUID;
  frequency: Frequency;
  current: number;
  longest: number;
  alive: boolean;
  last_period: ISODate | null;
  total_completions: number;
}

export interface Badge {
  code: string;
  name: string;
  description: string;
  icon: string;
  awarded_at: ISODateTime;
}

export interface CategoryCount {
  category: Category;
  completions: number;
}

export interface PersonalInsights {
  from: ISODate;
  to: ISODate;
  totals: { completions: number; active_days: number; total_value: number; consistency_rate: number };
  daily: { date: ISODate; completions: number; value: number }[];
  by_category: CategoryCount[];
  streaks: Streak[];
  badges: Badge[];
}

export interface TeamInsightsDay {
  date: ISODate;
  completions: number | null;
  active_members: number | null;
  suppressed: boolean;
}

export interface TeamInsights {
  team_id: UUID;
  from: ISODate;
  to: ISODate;
  min_cohort_size: number;
  totals: { completions: number; active_days: number; suppressed_days: number; avg_active_members: number };
  daily: TeamInsightsDay[];
  by_category: CategoryCount[];
  /** Categories withheld from `by_category` because fewer than `min_cohort_size` members contributed. */
  suppressed_categories?: Category[];
}

export interface OrgInsightsTeam {
  team_id: UUID;
  completions: number;
  active_days: number;
  suppressed_days: number;
  avg_active_members: number;
}

export interface OrgInsights {
  from: ISODate;
  to: ISODate;
  min_cohort_size: number;
  teams: OrgInsightsTeam[];
}

export interface InsightsQuery {
  from?: ISODate;
  to?: ISODate;
  category?: Category;
}

// ---------------------------------------------------------------- notifications

export type NotificationType =
  | 'welcome'
  | 'reminder'
  | 'badge.awarded'
  | 'streak.milestone'
  | 'challenge.created'
  | 'challenge.joined'
  | 'challenge.goal_reached';

export interface NotificationOut {
  id: UUID;
  type: NotificationType | string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  is_read: boolean;
  created_at: ISODateTime;
}

export interface NotificationPreferences {
  reminders_enabled: boolean;
  reminder_hour: number;
  timezone: string;
  email_enabled: boolean;
}

export interface NotificationListQuery extends PageQuery {
  unread_only?: boolean;
}

// ---------------------------------------------------------------- RFC 7807

export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  code?: string;
  instance?: string;
  request_id?: string;
  errors?: ProblemFieldError[] | Record<string, unknown>;
}

export interface ProblemFieldError {
  loc?: (string | number)[];
  field?: string;
  msg?: string;
  message?: string;
  type?: string;
}
