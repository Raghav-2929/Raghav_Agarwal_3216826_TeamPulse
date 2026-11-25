# TeamPulse — REST API Contract (v1)

All traffic enters through the **API Gateway** (`http://localhost:8000` locally, the ALB/CloudFront
`/api/*` behaviour in AWS). Every service exposes the *same* path it is reached through, so the
gateway forwards paths unchanged.

## Conventions

| Topic | Rule |
|---|---|
| Base path | `/api/v1` |
| Auth | `Authorization: Bearer <access_token>` (RS256 JWT, 15 min). Public: `POST /auth/login`, `POST /auth/refresh`, `GET /.well-known/jwks.json`, `/health/*` |
| JSON casing | `snake_case` |
| IDs | UUID strings |
| Dates | `YYYY-MM-DD` (`date`), ISO-8601 UTC (`datetime`) |
| Pagination | query `page` (1-based, default 1), `size` (default 20, max 100) → `{ "items": [], "total": 0, "page": 1, "size": 20 }` |
| Errors | RFC 7807 `application/problem+json` → `{ "type", "title", "status", "detail", "code", "instance", "request_id", "errors"? }` |
| Correlation | `X-Request-ID` accepted/echoed on every response |
| Roles | `employee`, `manager`, `admin` |

### JWT access-token claims

```json
{
  "sub": "5d1c…", "name": "Alice Johnson", "email": "alice@teampulse.io",
  "role": "employee", "team_id": "a1b2…", "team_name": "Engineering",
  "managed_team_ids": [], "iss": "teampulse-identity", "aud": "teampulse",
  "iat": 1762560000, "exp": 1762560900, "jti": "…", "typ": "access"
}
```

### Enumerations

| Name | Values |
|---|---|
| `category` (activity type) | `fitness`, `mindfulness`, `nutrition`, `sleep`, `hydration`, `learning` |
| `frequency` | `daily`, `weekly` |
| `visibility` | `private`, `team` |
| `challenge status` | `upcoming`, `active`, `completed` |
| `badge criterion` | `streak_days`, `total_completions`, `category_completions` |

---

## Identity Service (`identity-service`)

`UserOut`
```json
{ "id": "uuid", "email": "alice@teampulse.io", "full_name": "Alice Johnson", "role": "employee",
  "team_id": "uuid|null", "team_name": "Engineering|null", "is_active": true, "created_at": "datetime" }
```
`TokenResponse`
```json
{ "access_token": "jwt", "refresh_token": "opaque", "token_type": "bearer", "expires_in": 900, "user": UserOut }
```

| Method | Path | Roles | Body / Query | Response |
|---|---|---|---|---|
| POST | `/api/v1/auth/login` | public | `{email, password}` | 200 `TokenResponse` · 401 `invalid_credentials` · 423 `account_locked` |
| POST | `/api/v1/auth/refresh` | public | `{refresh_token}` | 200 `TokenResponse` (refresh token rotated) · 401 |
| POST | `/api/v1/auth/logout` | any | `{refresh_token}` | 204 |
| GET | `/api/v1/users/me` | any | – | 200 `UserOut` |
| PATCH | `/api/v1/users/me` | any | `{full_name}` | 200 `UserOut` |
| POST | `/api/v1/users/me/password` | any | `{current_password, new_password}` | 204 |
| GET | `/api/v1/users` | admin | `role, team_id, search, page, size` | 200 `Page[UserOut]` |
| POST | `/api/v1/users` | admin | `{email, full_name, password, role, team_id?}` | 201 `UserOut` · 409 `email_taken` |
| GET | `/api/v1/users/{id}` | admin | – | 200 `UserOut` |
| PATCH | `/api/v1/users/{id}` | admin | `{full_name?, role?, team_id?, is_active?}` | 200 `UserOut` |
| GET | `/api/v1/teams` | any | – | 200 `[{id, name, description, manager_id, manager_name, member_count}]` |
| POST | `/api/v1/teams` | admin | `{name, description?, manager_id?}` | 201 `TeamOut` |
| PATCH | `/api/v1/teams/{id}` | admin | `{name?, description?, manager_id?}` | 200 `TeamOut` |
| GET | `/api/v1/teams/{id}/members` | manager of team, admin | – | 200 `[{id, full_name, role}]` (no wellness data) |
| GET | `/.well-known/jwks.json` | public | – | 200 JWKS |

Password policy: ≥ 8 chars, upper + lower + digit. Five failed logins lock the account for 15 minutes.

## Habit Service (`habit-service`)

`HabitOut`
```json
{ "id": "uuid", "owner_id": "uuid", "owner_name": "Alice Johnson", "team_id": "uuid|null",
  "title": "Morning run", "description": "5k before work", "category": "fitness",
  "frequency": "daily", "target_per_period": 1, "visibility": "private", "color": "#4F46E5",
  "is_archived": false, "created_at": "datetime", "updated_at": "datetime" }
```

| Method | Path | Roles | Body / Query | Response |
|---|---|---|---|---|
| GET | `/api/v1/habits` | any (own habits) | `category, visibility, include_archived=false, search, page, size` | 200 `Page[HabitOut]` |
| POST | `/api/v1/habits` | any | `{title(3-80), description?(≤500), category, frequency, target_per_period, visibility, color?}` | 201 `HabitOut` |
| GET | `/api/v1/habits/team` | any | `category, search, page, size` | 200 `Page[HabitOut]` — teammates' `team`-visible habits |
| GET | `/api/v1/habits/{id}` | owner; teammates if `visibility=team` | – | 200 `HabitOut` · 404 |
| PATCH | `/api/v1/habits/{id}` | owner | any subset of create fields + `is_archived` | 200 `HabitOut` |
| DELETE | `/api/v1/habits/{id}` | owner | – | 204 (soft-archive) |

Rules: `daily` ⇒ `target_per_period = 1`; `weekly` ⇒ `1..7`. Private habits are never returned to anyone but the owner (404, not 403, to avoid existence leaks).

## Event Tracking Service (`event-tracking-service`)

`ActivityOut`
```json
{ "id": "uuid", "habit_id": "uuid", "category": "fitness", "value": 1.0, "note": "felt great",
  "completed_on": "2026-11-08", "occurred_at": "datetime", "created_at": "datetime" }
```

| Method | Path | Roles | Body / Query | Response |
|---|---|---|---|---|
| POST | `/api/v1/activities` | any (own habits) | `{habit_id, completed_on?=today, value?=1, note?(≤280)}` | 201 `ActivityOut` · 404 habit · 409 `already_logged` · 422 `invalid_date`/`habit_archived` · 503 `dependency_unavailable` |
| GET | `/api/v1/activities` | any (own) | `habit_id, category, from, to, page, size` | 200 `Page[ActivityOut]` |

`completed_on` may not be in the future, nor older than `ACTIVITY_BACKFILL_DAYS` (default 7).
One completion per habit per day (idempotent; duplicates → 409).

## Challenge Service (`challenge-service`)

`ChallengeOut`
```json
{ "id": "uuid", "title": "November Step-Up", "description": "…", "category": "fitness|null",
  "team_id": "uuid|null", "team_name": "Engineering|null", "starts_on": "date", "ends_on": "date",
  "target_count": 20, "status": "active", "created_by": "uuid", "created_at": "datetime",
  "participant_count": 7, "joined": true, "my_score": 5, "my_goal_reached": false,
  "show_on_leaderboard": true }
```
`LeaderboardOut`
```json
{ "challenge_id": "uuid", "my_rank": 2,
  "individuals": [ { "rank": 1, "display_name": "Alice Johnson", "team_name": "Engineering", "score": 12, "goal_reached": false, "is_me": false } ],
  "teams": [ { "rank": 1, "team_id": "uuid", "team_name": "Engineering", "participants": 4, "total_score": 31, "average_score": 7.75 } ] }
```
`BadgeRuleOut`
```json
{ "code": "week_warrior", "name": "Week Warrior", "description": "7-day streak", "icon": "🔥",
  "criterion": "streak_days", "category": null, "threshold": 7, "is_active": true }
```

| Method | Path | Roles | Body / Query | Response |
|---|---|---|---|---|
| GET | `/api/v1/challenges` | any | `status, category, search, joined, from, to, page, size` | 200 `Page[ChallengeOut]` (org-wide + own team) |
| POST | `/api/v1/challenges` | manager (own team or org-wide), admin | `{title, description?, category?, team_id?, starts_on, ends_on, target_count}` | 201 `ChallengeOut` |
| GET | `/api/v1/challenges/{id}` | any in scope | – | 200 `ChallengeOut` |
| PATCH | `/api/v1/challenges/{id}` | creator, admin | `{title?, description?, ends_on?, target_count?}` | 200 |
| DELETE | `/api/v1/challenges/{id}` | creator (upcoming only), admin | – | 204 |
| POST | `/api/v1/challenges/{id}/join` | any in scope | `{show_on_leaderboard=true}` | 201 `ChallengeOut` · 409 `already_joined` · 422 `challenge_completed` |
| PATCH | `/api/v1/challenges/{id}/participation` | participant | `{show_on_leaderboard}` | 200 `ChallengeOut` |
| DELETE | `/api/v1/challenges/{id}/participation` | participant | – | 204 |
| GET | `/api/v1/challenges/{id}/leaderboard` | any in scope | `limit=20` | 200 `LeaderboardOut` — opted-out participants appear as "Anonymous participant" |
| GET | `/api/v1/badge-rules` | any | – | 200 `[BadgeRuleOut]` |
| PUT | `/api/v1/badge-rules/{code}` | admin | `BadgeRuleOut` minus `code` | 200 (upsert) |
| DELETE | `/api/v1/badge-rules/{code}` | admin | – | 204 |

## Insight Service (`insight-service`)

`PersonalInsights`
```json
{ "from": "date", "to": "date",
  "totals": { "completions": 42, "active_days": 20, "total_value": 42.0, "consistency_rate": 0.67 },
  "daily": [ { "date": "2026-11-01", "completions": 2, "value": 2.0 } ],
  "by_category": [ { "category": "fitness", "completions": 18 } ],
  "streaks": [ { "habit_id": "uuid", "frequency": "daily", "current": 5, "longest": 9, "alive": true, "last_period": "2026-11-08", "total_completions": 31 } ],
  "badges": [ { "code": "week_warrior", "name": "Week Warrior", "description": "…", "icon": "🔥", "awarded_at": "datetime" } ] }
```
`TeamInsights` (aggregated only, k-anonymised)
```json
{ "team_id": "uuid", "from": "date", "to": "date", "min_cohort_size": 3,
  "totals": { "completions": 120, "active_days": 25, "suppressed_days": 3, "avg_active_members": 3.4 },
  "daily": [ { "date": "2026-11-01", "completions": 9, "active_members": 4, "suppressed": false },
             { "date": "2026-11-02", "completions": null, "active_members": null, "suppressed": true } ],
  "by_category": [ { "category": "fitness", "completions": 50 } ],
  "suppressed_categories": [ "sleep" ] }
```

| Method | Path | Roles | Query | Response |
|---|---|---|---|---|
| GET | `/api/v1/insights/me` | any | `from, to, category` (default last 30 days, max 180) | 200 `PersonalInsights` |
| GET | `/api/v1/insights/me/streaks` | any | – | 200 `[Streak]` |
| GET | `/api/v1/insights/me/badges` | any | – | 200 `[Badge]` |
| GET | `/api/v1/insights/teams/{team_id}` | manager of that team, admin | `from, to, category` | 200 `TeamInsights` · 403 |
| GET | `/api/v1/insights/org` | admin | `from, to` | 200 `{from, to, min_cohort_size, teams: [{team_id, completions, active_days, suppressed_days, avg_active_members}]}` |

Days with fewer than `MIN_COHORT_SIZE` (3) distinct active members — **including zero** — are suppressed
entirely, so a manager can never infer one person's activity (or that everyone was inactive). With a
`category` filter, k applies to members active in that category. Categories with fewer than k distinct
members over the whole range are omitted from `by_category` and listed in `suppressed_categories`.

## Notification Service (`notification-service`)

`NotificationOut`
```json
{ "id": "uuid", "type": "badge.awarded", "title": "New badge: Week Warrior 🔥", "body": "…",
  "data": {}, "is_read": false, "created_at": "datetime" }
```

| Method | Path | Roles | Body / Query | Response |
|---|---|---|---|---|
| GET | `/api/v1/notifications` | any (own) | `unread_only=false, page, size` | 200 `Page[NotificationOut]` |
| GET | `/api/v1/notifications/unread-count` | any | – | 200 `{count}` |
| POST | `/api/v1/notifications/{id}/read` | owner | – | 200 `NotificationOut` |
| POST | `/api/v1/notifications/read-all` | any | – | 200 `{updated}` |
| GET | `/api/v1/notifications/preferences` | any | – | 200 `{reminders_enabled, reminder_hour, timezone, email_enabled}` |
| PUT | `/api/v1/notifications/preferences` | any | same shape | 200 |

Notification `type` values: `welcome`, `reminder`, `badge.awarded`, `streak.milestone`,
`challenge.created`, `challenge.joined`, `challenge.goal_reached`.

## Gateway

| Method | Path | Notes |
|---|---|---|
| GET | `/health/live` | process liveness (ALB target-group health check) |
| GET | `/health/ready` | own readiness → `{status, checks}` |
| GET | `/health/services` | downstream status → `{status, services: {name: "up"|"down"|"circuit_open"}}` (503 if any is not up) |
| GET | `/docs` | Swagger UI for **every** service (dropdown), specs proxied from `/openapi/<service>.json` |
| * | `/api/v1/**` | routed by prefix (table below); JWT validated at the edge, `/internal/**` blocked, rate limited (`X-RateLimit-*`, 429 + `Retry-After`), body ≤ 1 MB (413) |

| Prefix | Upstream |
|---|---|
| `/api/v1/auth`, `/api/v1/users`, `/api/v1/teams`, `/.well-known` | identity-service |
| `/api/v1/habits` | habit-service |
| `/api/v1/activities` | event-tracking-service |
| `/api/v1/challenges`, `/api/v1/badge-rules` | challenge-service |
| `/api/v1/insights` | insight-service |
| `/api/v1/notifications` | notification-service |
