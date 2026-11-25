# Security & privacy

## 1. Who can see what

| Data | Employee (self) | Teammate | Manager of the team | Admin |
|---|---|---|---|---|
| Own habits (private) | ✅ | ❌ (404) | ❌ (404) | ❌ |
| Habits shared with the team (`visibility=team`) | ✅ | ✅ title, owner name | ✅ as a team member only | ❌ |
| Activity history, notes | ✅ | ❌ | ❌ | ❌ |
| Personal streaks, badges, trends | ✅ | ❌ | ❌ | ❌ |
| Team trends | ❌ | ❌ | ✅ **aggregated, k-anonymised** | ✅ aggregated |
| Organisation trends (per team) | ❌ | ❌ | ❌ | ✅ aggregated |
| Team roster | ❌ | ❌ | ✅ names + roles only | ✅ |
| Challenge leaderboard | ✅ | ✅ | ✅ | ✅ — opted-out participants shown as "Anonymous participant" |
| Users, teams, badge rules administration | ❌ | ❌ | create challenges for own team / org | ✅ |

### k-anonymity for manager views
A team-day bucket is released only if **≥ k (default 3) distinct members** contributed; otherwise
completions *and* member counts are `null` (`suppressed: true`). This includes zero-activity days
(releasing "0" would reveal that every member was inactive). With a category filter, k applies to
members active in that category; per-category totals need k distinct members over the whole range.
Distinct counting uses pseudonymous id sets in DynamoDB that the API never returns.

### Data minimisation
* Events carry ids, categories and counts — never notes or habit titles.
* Private notes stay in the event-tracking database; logs redact `password`, `token`, `note` fields.
* JWTs contain name, role and team ids only — no wellness data.

## 2. Authentication & authorization

* Login with bcrypt-hashed passwords (cost 12); constant-time path for unknown e-mails (no account
  enumeration); **5 failures ⇒ 15-minute lockout** (423); failures logged as `auth.login_failed`
  (CloudWatch metric + alarm).
* **RS256 access tokens (15 min)**, `iss`/`aud`/`exp`/`typ` validated; JWKS endpoint for public keys;
  `kid` header for rotation. Only identity-service holds the private key (Secrets Manager).
* **Refresh tokens**: opaque, stored as SHA-256 hashes, rotated on every use, **reuse of a rotated token
  revokes the whole family**; logout and password change revoke them.
* Tokens are validated at the gateway **and** again in each service (zero trust between tiers).
* RBAC via `require_roles` plus resource-level checks (ownership, team membership, managed teams).
  Private resources return **404** so their existence is not disclosed.

## 3. Platform hardening

| Area | Control |
|---|---|
| Edge | gateway rate limits (300/min/user, 10 logins/min/IP), 1 MB body limit, `/internal/**` blocked, spoofable headers stripped; AWS: CloudFront + optional WAF, ALB accepts only requests carrying the CloudFront secret header |
| Transport | HTTPS at CloudFront/ALB (TLS 1.2+ policy), RDS `rds.force_ssl=1` (`DB_SSL=require`) |
| Network | 3 subnet tiers, SG chaining (ALB → gateway → services → RDS), NACLs per tier, no public IPs on tasks, data tier without internet route, optional VPC endpoints |
| Secrets | Secrets Manager, injected by ECS at start; each service's execution role reads only its own secrets |
| IAM | one execution + one task role per service (e.g. insight can only `GetItem/Query` the analytics table) |
| Containers | non-root user 10001, slim images, read-only root FS in ECS, ECR scan on push, immutable tags |
| Responses | RFC 7807 errors without stack traces; `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy`, `Cache-Control: no-store` |
| Audit/ops | JSON logs with request ids to CloudWatch; alarms on auth failures, 5xx, latency, DLQs |

## 4. Threats considered

| Threat | Mitigation |
|---|---|
| Manager infers an employee's wellness behaviour | aggregates only, k-anonymity incl. zero days, no per-person endpoints for managers |
| Credential stuffing / brute force | login rate limit per IP, account lockout, alarm on `AuthFailures` |
| Stolen refresh token | rotation + reuse detection revokes all sessions of that user |
| Forged tokens from a compromised service | asymmetric keys: services cannot sign |
| IDOR on habits/activities/notifications | every query scoped by `principal.user_id` / team; 404 on mismatch |
| Event replay / duplicates | inbox + DynamoDB conditional writes |
| Bypassing CloudFront to hit the ALB | ALB listener requires `X-Origin-Verify`; default action 403 |
| Lateral movement to the database | RDS SG allows only the services SG; per-service DB logins own only their DB |
