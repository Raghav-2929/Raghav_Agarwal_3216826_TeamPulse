# Inter-service communication

TeamPulse uses **synchronous HTTP only where an immediate answer is required** and **asynchronous
events everywhere else**. Event types, payloads and routing are catalogued in [events.md](events.md).

## 1. Synchronous calls

| Caller → callee | Why synchronous | Protection |
|---|---|---|
| Browser → gateway → any service | user request/response | edge JWT validation, rate limiting, per-upstream circuit breaker, 10 s timeout, body limit |
| event-tracking → habit (`GET /api/v1/habits/{id}`) | must reject logging someone else's / archived / unknown habit *before* accepting the write | caller's own JWT forwarded (habit applies its visibility rules), 2 s timeout, 2 retries (GET only, jittered backoff), circuit breaker (5 failures → open 20 s) → **503 `dependency_unavailable`** |
| all services → identity JWKS | public key for JWT verification | cached 10 min, refetched on unknown `kid` (≤ every 30 s) |

Service URLs: static (local), Consul lookups with client-side load balancing (Docker), ECS Service
Connect DNS names `http://<service>:8000` (AWS).

## 2. Asynchronous events

```
producer transaction ──► outbox_events ──relay──► bus ──► per-consumer queue ──► inbox (processed_events) ──► handler
```

* **Envelope:** `{id, type, source, version, time, subject, correlation_id, data}` (CloudEvents-like).
  `correlation_id` carries the originating `X-Request-ID`, so one request can be followed through every
  service's logs.
* **Transactional outbox** (identity, event-tracking, challenge): the event row commits with the
  business change; a relay publishes it afterwards (woken immediately after commit, 1 s poll as
  fallback, `SELECT … FOR UPDATE SKIP LOCKED` on Postgres so replicas never double-publish).
* **Idempotent inbox** (habit, challenge, notification): the event id is inserted into
  `processed_events` in the *same* transaction as the handler's writes → each event takes effect
  exactly once even though delivery is at-least-once.
* **Lambda idempotency:** the streak processor claims `EVENT#<id>` with a DynamoDB conditional write
  (TTL 7 days); on failure it releases the claim so the EventBridge retry reprocesses.
* **Dead letters:** RabbitMQ DLX per queue; SQS redrive after 5 receives; Lambda on-failure SQS DLQ.
  EventBridge archive allows replay after a fix.

### Delivery semantics and ordering
* At-least-once delivery, exactly-once *effects* (inbox / conditional writes).
* No global ordering is assumed: streaks are recomputed from the full (bounded) completion history, so
  an out-of-order or late back-filled completion still yields the correct streak.
* Consumers tolerate unknown fields (`extra="ignore"`) — producers can add fields without breaking them.

## 3. Failure scenarios

| Failure | Behaviour |
|---|---|
| habit-service down | event-tracking returns 503 fast after the breaker opens; nothing is written; UI shows the problem detail |
| Broker / EventBridge unavailable | activities still succeed (outbox keeps the events, `attempts` incremented); published when the bus recovers |
| Streak processor fails | EventBridge/SQS retries; after retries → DLQ + CloudWatch alarm; claim released so retry is safe |
| Duplicate delivery | skipped by inbox / DynamoDB claim (logged as `event.duplicate_skipped`) |
| Notification service down | messages wait in its SQS queue (alarm on queue depth/age); no data lost |
| A service is unhealthy behind the gateway | gateway breaker opens for that upstream only → 503 with `Retry-After`; `/health/services` shows `circuit_open` |

## 4. Assumptions

* Eventual consistency of ~1 s between logging an activity and seeing streaks/insights is acceptable.
* Events carry identifiers, categories and counts only — never notes or habit titles; e-mail addresses
  appear only in `user.*` events consumed by the notification service.
* The analytics table is owned by the streak processor (writer) and read by insight-service; this
  shared-store exception to database-per-service is the CQRS read model.
* Badge rules are owned by challenge-service and pushed to the processor via `badge_rules.changed`
  (re-published on every start, so a lost update self-heals).
