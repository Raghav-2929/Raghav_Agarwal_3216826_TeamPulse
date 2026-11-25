# API documentation

Every API call goes through the **API gateway**: `http://localhost:8000` locally, or
`https://<cloudfront-domain>/api/...` in AWS. Paths start with `/api/v1`.

There are three ways to read and try the API:

| Option | Where | Best for |
|---|---|---|
| Swagger UI (live) | http://localhost:8000/docs | Reading and trying endpoints in the browser |
| OpenAPI files | [docs/openapi/](openapi) | Importing into tools (Swagger Editor, Postman, code generators) |
| Postman collection | [postman/](../postman) | Running all success and failure scenarios in one go |

The full reference (rules, every endpoint, roles, request and response shapes) is in
[api-contract.md](api-contract.md).

## 1. Swagger UI

1. Start the system ([setup guide](setup-guide.md)) and open http://localhost:8000/docs.
2. Pick a service in the **Select a definition** list (top right).
3. Get a token: in **identity-service**, run `POST /api/v1/auth/login` with
   `{"email": "alice.johnson@teampulse.io", "password": "TeamPulse@2026"}` and copy `access_token`.
4. Click **Authorize**, paste the token, and call any endpoint. The token is valid for 15 minutes.

## 2. OpenAPI files (OpenAPI 3.1)

| Service | Paths | Operations | File |
|---|---|---|---|
| identity-service | `/api/v1/auth`, `/api/v1/users`, `/api/v1/teams`, `/.well-known/jwks.json` | 17 | [identity-service.json](openapi/identity-service.json) |
| habit-service | `/api/v1/habits` | 8 | [habit-service.json](openapi/habit-service.json) |
| event-tracking-service | `/api/v1/activities` | 4 | [event-tracking-service.json](openapi/event-tracking-service.json) |
| challenge-service | `/api/v1/challenges`, `/api/v1/badge-rules` | 14 | [challenge-service.json](openapi/challenge-service.json) |
| insight-service | `/api/v1/insights` | 7 | [insight-service.json](openapi/insight-service.json) |
| notification-service | `/api/v1/notifications` | 8 | [notification-service.json](openapi/notification-service.json) |

58 operations in total, including each service's `/health/live` and `/health/ready`. The files are a
copy of what each running service serves at `/openapi.json` (the gateway shows them at
`/openapi/<service>.json`). To view one without running anything, paste it into
https://editor.swagger.io.

## 3. Postman collection

| File | What |
|---|---|
| [TeamPulse.postman_collection.json](../postman/TeamPulse.postman_collection.json) | 73 requests in 9 folders, with tests |
| [TeamPulse.local.postman_environment.json](../postman/TeamPulse.local.postman_environment.json) | `baseUrl = http://localhost:8000` |

**In Postman:** *Import* both files → choose the environment **TeamPulse — local** (top right) →
open the collection → *Run*. It creates the habits, challenge and user it needs.

**From the command line:**

```bash
npx newman run postman/TeamPulse.postman_collection.json -e postman/TeamPulse.local.postman_environment.json
```

The requests log in as each role, save the tokens and ids, and use them in later requests. Each
folder checks the happy path **and** the failures:

| Folder | Examples of what it checks |
|---|---|
| Health & discovery | gateway and service health, public signing key (JWKS) |
| Auth | login as each role, wrong password (401), invalid input (422), refresh-token rotation, replaying an old refresh token (rejected) |
| Users & teams | admin creates a user; an employee cannot (403) |
| Habits | private vs team habits; a teammate cannot see a private habit (404) |
| Activities | log a completion; the same habit twice on one day (409); a future date (422) |
| Challenges & leaderboards | manager creates (employee gets 403), join, join twice (409), leaderboard with anonymous opt-out, badge rules |
| Insights | personal analytics; manager sees only aggregated team data; employee blocked (403) |
| Notifications | list, unread count, mark read, preferences |
| Security & cross-cutting | missing or tampered token (401), internal routes blocked (404), request id echoed, security headers |

To test with AWS, duplicate the environment and set `baseUrl` to `https://<cloudfront-domain>`.

## 4. Conventions in one place

| Topic | Rule |
|---|---|
| Authentication | `Authorization: Bearer <access_token>`. Public: `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `GET /.well-known/jwks.json`, `/health/*` |
| Roles | `employee`, `manager`, `admin` (inside the token) |
| Lists | `?page=1&size=20` → `{"items": [...], "total": 0, "page": 1, "size": 20}` |
| Errors | `application/problem+json` (RFC 7807) with a `code` and the `request_id` |
| Tracing | send or receive `X-Request-ID`; the same id appears in every service's logs |

Example error:

```json
{
  "type": "https://docs.teampulse.io/problems/already_logged",
  "title": "Conflict",
  "status": 409,
  "detail": "This habit is already logged for that day",
  "code": "already_logged",
  "instance": "/api/v1/activities",
  "request_id": "3f6b1c2d9a8e4f7b8c0d1e2f3a4b5c6d"
}
```
