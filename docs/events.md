# TeamPulse — Integration Event Catalog (v1)

Events are published to a single logical bus, **`teampulse-events`**:

| Environment | Transport | Routing |
|---|---|---|
| Unit tests | in-memory bus | handler registry |
| Local (no Docker) | `direct` driver — HTTP POST to each subscriber's `/internal/events` | `EVENT_ROUTES` env map |
| Docker Compose | RabbitMQ topic exchange `teampulse.events` (routing key = event type), one durable queue per consumer + DLX | queue bindings |
| AWS | Amazon EventBridge bus `teampulse-events` (`detail-type` = event type, `source` = `teampulse.<service>`) | EventBridge rules → Lambda / SQS queue per consumer (+ DLQ) |

Delivery is **at-least-once**. Producers that own a database use the **transactional outbox**;
consumers that own a database use an **inbox** (`processed_events`) so effects are applied exactly once.

## Envelope (CloudEvents-inspired)

```json
{
  "id": "8f0f8c1e-…",              // unique event id (dedupe key)
  "type": "activity.completed",    // routing key / detail-type
  "source": "event-tracking-service",
  "version": 1,
  "time": "2026-11-08T07:31:02.114Z",
  "subject": "user:5d1c…",         // pseudonymous subject
  "correlation_id": "req-…",       // X-Request-ID of the originating call
  "data": { … }
}
```

Events carry **IDs, categories and counts only** — never habit titles, notes or e-mail addresses
(except `user.registered`, consumed solely by the Notification Service's contact projection).

## Catalog

| Type | Producer | Consumers | `data` |
|---|---|---|---|
| `user.registered` | identity | notification | `user_id, team_id, role, display_name, email` |
| `user.updated` | identity | notification, habit (refreshes denormalised owner name / team) | `user_id, team_id, role, display_name, email, is_active` |
| `activity.completed` | event-tracking | streak-processor (Lambda), notification | `activity_id, user_id, team_id, habit_id, category, frequency, target_per_period, value, completed_on, occurred_at` |
| `progress.updated` | streak-processor | challenge | `activity_id, user_id, team_id, habit_id, category, completed_on, value, current_streak` |
| `streak.milestone` | streak-processor | notification | `user_id, habit_id, streak, frequency` |
| `badge.awarded` | streak-processor | notification | `user_id, code, name, description, icon` |
| `badge_rules.changed` | challenge | streak-processor | `rules: [BadgeRule]` (event-carried state transfer) |
| `challenge.created` | challenge | notification | `challenge_id, title, team_id, starts_on, ends_on, created_by` |
| `challenge.joined` | challenge | notification | `challenge_id, title, user_id` |
| `challenge.goal_reached` | challenge | notification | `challenge_id, title, user_id, score` |
| `reminder.tick` | scheduler (EventBridge Scheduler / local loop) | notification | `hour_utc` |

## Analytics single-table (DynamoDB `teampulse-analytics`)

Written only by the streak processor, read only by the Insight Service.

| PK | SK | Attributes |
|---|---|---|
| `USER#<user>` | `STREAK#<habit>` | `frequency, target, dates[], current, longest, last_period, total` |
| `USER#<user>` | `STATS` | `total, cat_<category>` |
| `USER#<user>` | `DAY#<yyyy-mm-dd>` | `completions, value, cat_<category>` |
| `USER#<user>` | `BADGE#<code>` | `name, description, icon, awarded_at` |
| `TEAM#<team>` | `DAY#<yyyy-mm-dd>` | `completions, value, cat_<category>, active_users{}, active_users_cat_<category>{}` (sets used only to count distinct members for k-anonymity) |
| `ORG` | `TEAMS` | `team_ids{}` (index for the admin org view — avoids a table scan) |
| `CONFIG` | `BADGE_RULES` | `rules[]` |
| `EVENT#<id>` | `PROCESSED` | `expires_at` (TTL, idempotency) |
