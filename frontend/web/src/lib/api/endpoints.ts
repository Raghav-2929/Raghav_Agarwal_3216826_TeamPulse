import type { HttpClient } from './http';
import type {
  ActivityCreate,
  ActivityListQuery,
  ActivityOut,
  Badge,
  BadgeRuleOut,
  BadgeRuleUpsert,
  ChallengeCreate,
  ChallengeListQuery,
  ChallengeOut,
  ChallengeUpdate,
  HabitCreate,
  HabitListQuery,
  HabitOut,
  HabitUpdate,
  InsightsQuery,
  LeaderboardOut,
  LoginRequest,
  NotificationListQuery,
  NotificationOut,
  NotificationPreferences,
  OrgInsights,
  Page,
  PasswordChange,
  PersonalInsights,
  Streak,
  TeamCreate,
  TeamHabitListQuery,
  TeamInsights,
  TeamMember,
  TeamOut,
  TeamUpdate,
  TokenResponse,
  UserCreate,
  UserListQuery,
  UserOut,
  UserUpdate,
  UUID,
} from './types';

type Opts = { signal?: AbortSignal };
const V1 = '/api/v1';
const id = (value: string) => encodeURIComponent(value);

/** Typed wrappers for every endpoint of the REST contract v1. */
export function createApi(http: HttpClient) {
  return {
    auth: {
      login: (body: LoginRequest) => http.post<TokenResponse>(`${V1}/auth/login`, body, { auth: false }),
      refresh: (refresh_token: string) => http.post<TokenResponse>(`${V1}/auth/refresh`, { refresh_token }, { auth: false }),
      logout: (refresh_token: string) =>
        http.post<void>(`${V1}/auth/logout`, { refresh_token }, { retryOnUnauthorized: false }),
    },

    users: {
      me: (o?: Opts) => http.get<UserOut>(`${V1}/users/me`, o),
      updateMe: (body: { full_name: string }) => http.patch<UserOut>(`${V1}/users/me`, body),
      changePassword: (body: PasswordChange) => http.post<void>(`${V1}/users/me/password`, body),
      list: (query: UserListQuery = {}, o?: Opts) => http.get<Page<UserOut>>(`${V1}/users`, { ...o, query: { ...query } }),
      create: (body: UserCreate) => http.post<UserOut>(`${V1}/users`, body),
      get: (userId: UUID, o?: Opts) => http.get<UserOut>(`${V1}/users/${id(userId)}`, o),
      update: (userId: UUID, body: UserUpdate) => http.patch<UserOut>(`${V1}/users/${id(userId)}`, body),
    },

    teams: {
      list: (o?: Opts) => http.get<TeamOut[]>(`${V1}/teams`, o),
      create: (body: TeamCreate) => http.post<TeamOut>(`${V1}/teams`, body),
      update: (teamId: UUID, body: TeamUpdate) => http.patch<TeamOut>(`${V1}/teams/${id(teamId)}`, body),
      members: (teamId: UUID, o?: Opts) => http.get<TeamMember[]>(`${V1}/teams/${id(teamId)}/members`, o),
    },

    habits: {
      list: (query: HabitListQuery = {}, o?: Opts) => http.get<Page<HabitOut>>(`${V1}/habits`, { ...o, query: { ...query } }),
      team: (query: TeamHabitListQuery = {}, o?: Opts) => http.get<Page<HabitOut>>(`${V1}/habits/team`, { ...o, query: { ...query } }),
      get: (habitId: UUID, o?: Opts) => http.get<HabitOut>(`${V1}/habits/${id(habitId)}`, o),
      create: (body: HabitCreate) => http.post<HabitOut>(`${V1}/habits`, body),
      update: (habitId: UUID, body: HabitUpdate) => http.patch<HabitOut>(`${V1}/habits/${id(habitId)}`, body),
      /** Soft-archives the habit (204). */
      archive: (habitId: UUID) => http.delete<void>(`${V1}/habits/${id(habitId)}`),
    },

    activities: {
      create: (body: ActivityCreate) => http.post<ActivityOut>(`${V1}/activities`, body),
      list: (query: ActivityListQuery = {}, o?: Opts) => http.get<Page<ActivityOut>>(`${V1}/activities`, { ...o, query: { ...query } }),
    },

    challenges: {
      list: (query: ChallengeListQuery = {}, o?: Opts) => http.get<Page<ChallengeOut>>(`${V1}/challenges`, { ...o, query: { ...query } }),
      create: (body: ChallengeCreate) => http.post<ChallengeOut>(`${V1}/challenges`, body),
      get: (challengeId: UUID, o?: Opts) => http.get<ChallengeOut>(`${V1}/challenges/${id(challengeId)}`, o),
      update: (challengeId: UUID, body: ChallengeUpdate) => http.patch<ChallengeOut>(`${V1}/challenges/${id(challengeId)}`, body),
      remove: (challengeId: UUID) => http.delete<void>(`${V1}/challenges/${id(challengeId)}`),
      join: (challengeId: UUID, show_on_leaderboard = true) =>
        http.post<ChallengeOut>(`${V1}/challenges/${id(challengeId)}/join`, { show_on_leaderboard }),
      updateParticipation: (challengeId: UUID, show_on_leaderboard: boolean) =>
        http.patch<ChallengeOut>(`${V1}/challenges/${id(challengeId)}/participation`, { show_on_leaderboard }),
      leave: (challengeId: UUID) => http.delete<void>(`${V1}/challenges/${id(challengeId)}/participation`),
      leaderboard: (challengeId: UUID, limit = 20, o?: Opts) =>
        http.get<LeaderboardOut>(`${V1}/challenges/${id(challengeId)}/leaderboard`, { ...o, query: { limit } }),
    },

    badgeRules: {
      list: (o?: Opts) => http.get<BadgeRuleOut[]>(`${V1}/badge-rules`, o),
      upsert: (code: string, body: BadgeRuleUpsert) => http.put<BadgeRuleOut>(`${V1}/badge-rules/${id(code)}`, body),
      remove: (code: string) => http.delete<void>(`${V1}/badge-rules/${id(code)}`),
    },

    insights: {
      me: (query: InsightsQuery = {}, o?: Opts) => http.get<PersonalInsights>(`${V1}/insights/me`, { ...o, query: { ...query } }),
      streaks: (o?: Opts) => http.get<Streak[]>(`${V1}/insights/me/streaks`, o),
      badges: (o?: Opts) => http.get<Badge[]>(`${V1}/insights/me/badges`, o),
      team: (teamId: UUID, query: InsightsQuery = {}, o?: Opts) =>
        http.get<TeamInsights>(`${V1}/insights/teams/${id(teamId)}`, { ...o, query: { ...query } }),
      org: (query: { from?: string; to?: string } = {}, o?: Opts) => http.get<OrgInsights>(`${V1}/insights/org`, { ...o, query: { ...query } }),
    },

    notifications: {
      list: (query: NotificationListQuery = {}, o?: Opts) =>
        http.get<Page<NotificationOut>>(`${V1}/notifications`, { ...o, query: { ...query } }),
      unreadCount: (o?: Opts) => http.get<{ count: number }>(`${V1}/notifications/unread-count`, o),
      markRead: (notificationId: UUID) => http.post<NotificationOut>(`${V1}/notifications/${id(notificationId)}/read`),
      markAllRead: () => http.post<{ updated: number }>(`${V1}/notifications/read-all`),
      preferences: (o?: Opts) => http.get<NotificationPreferences>(`${V1}/notifications/preferences`, o),
      updatePreferences: (body: NotificationPreferences) => http.put<NotificationPreferences>(`${V1}/notifications/preferences`, body),
    },
  };
}

export type Api = ReturnType<typeof createApi>;
