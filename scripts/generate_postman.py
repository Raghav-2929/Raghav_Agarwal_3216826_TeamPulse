"""Generate the Postman collection + environment for TeamPulse (all endpoints, success AND failure cases).

    uv run python scripts/generate_postman.py

Requests are ordered so the whole collection can run top-to-bottom (Postman Runner or
``npx newman run postman/TeamPulse.postman_collection.json -e postman/TeamPulse.local.postman_environment.json``):
logins store tokens, creates store ids, later requests reuse them. Every request carries test assertions.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "postman"
PASSWORD = "TeamPulse@2026"


def tests(*lines: str) -> list[dict]:
    return [{"listen": "test", "script": {"type": "text/javascript", "exec": list(lines)}}]


def status(code: int) -> str:
    return f'pm.test("status {code}", () => pm.response.to.have.status({code}));'


def problem(code: str) -> str:
    return (
        f'pm.test("problem+json code={code}", () => {{ '
        f'pm.expect(pm.response.headers.get("Content-Type")).to.include("application/problem+json"); '
        f'pm.expect(pm.response.json().code).to.eql("{code}"); }});'
    )


def save(var: str, expr: str) -> str:
    return f'pm.collectionVariables.set("{var}", {expr});'


def req(
    name: str,
    method: str,
    path: str,
    *,
    auth_as: str | None = "employeeToken",
    body: dict | None = None,
    test: list[str] | None = None,
    description: str = "",
    headers: list[dict] | None = None,
) -> dict:
    raw_url = "{{baseUrl}}" + path
    path_part, _, query = path.partition("?")
    url: dict = {
        "raw": raw_url,
        "host": ["{{baseUrl}}"],
        "path": [p for p in path_part.strip("/").split("/") if p],
    }
    if query:
        url["query"] = [{"key": k, "value": v} for k, _, v in (q.partition("=") for q in query.split("&"))]
    request: dict = {"method": method, "header": list(headers or []), "url": url, "description": description}
    if auth_as:
        request["auth"] = {
            "type": "bearer",
            "bearer": [{"key": "token", "value": "{{" + auth_as + "}}", "type": "string"}],
        }
    else:
        request["auth"] = {"type": "noauth"}
    if body is not None:
        request["header"].append({"key": "Content-Type", "value": "application/json"})
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(body, indent=2, ensure_ascii=False),
            "options": {"raw": {"language": "json"}},
        }
    item = {"name": name, "request": request}
    if test:
        item["event"] = tests(*test)
    return item


def login(name: str, email: str, var: str, extra: list[str] | None = None) -> dict:
    return req(
        name,
        "POST",
        "/api/v1/auth/login",
        auth_as=None,
        body={"email": email, "password": PASSWORD},
        test=[status(200), save(var, "pm.response.json().access_token"), *(extra or [])],
    )


folders = [
    (
        "0 · Health & discovery",
        [
            req("Gateway liveness", "GET", "/health/live", auth_as=None, test=[status(200)]),
            req(
                "Downstream services status (circuit breakers)",
                "GET",
                "/health/services",
                auth_as=None,
                test=[
                    status(200),
                    'pm.test("all up", () => Object.values(pm.response.json().services)'
                    '.forEach(s => pm.expect(s).to.eql("up")));',
                ],
            ),
            req(
                "JWKS (public signing keys)",
                "GET",
                "/.well-known/jwks.json",
                auth_as=None,
                test=[
                    status(200),
                    'pm.test("RS256 key", () => pm.expect(pm.response.json().keys[0].alg).to.eql("RS256"));',
                ],
            ),
        ],
    ),
    (
        "1 · Auth",
        [
            login(
                "Login — employee (Alice)",
                "alice.johnson@teampulse.io",
                "employeeToken",
                [
                    save("employeeRefresh", "pm.response.json().refresh_token"),
                    save("employeeTeamId", "pm.response.json().user.team_id"),
                ],
            ),
            login("Login — employee, same team (Ben)", "ben.carter@teampulse.io", "teammateToken"),
            login("Login — employee, other team (Emma)", "emma.davis@teampulse.io", "otherTeamToken"),
            login(
                "Login — manager (Maya, Engineering)",
                "maya.patel@teampulse.io",
                "managerToken",
                [save("managerTeamId", "pm.response.json().user.team_id")],
            ),
            login("Login — admin", "admin@teampulse.io", "adminToken"),
            req(
                "Refresh — rotates the refresh token",
                "POST",
                "/api/v1/auth/refresh",
                auth_as=None,
                body={"refresh_token": "{{employeeRefresh}}"},
                test=[
                    status(200),
                    save("employeeToken", "pm.response.json().access_token"),
                    save("employeeRefreshRotated", "pm.response.json().refresh_token"),
                ],
            ),
            req(
                "Refresh — replaying a rotated token is rejected (theft detection)",
                "POST",
                "/api/v1/auth/refresh",
                auth_as=None,
                body={"refresh_token": "{{employeeRefresh}}"},
                test=[status(401), problem("invalid_refresh_token")],
            ),
            req(
                "Login — wrong password → 401",
                "POST",
                "/api/v1/auth/login",
                auth_as=None,
                body={"email": "alice.johnson@teampulse.io", "password": "wrong"},
                test=[status(401), problem("invalid_credentials")],
            ),
            req(
                "Login — validation error → 422",
                "POST",
                "/api/v1/auth/login",
                auth_as=None,
                body={"email": "not-an-email", "password": ""},
                test=[status(422), problem("validation_failed")],
            ),
            req(
                "Re-login employee (fresh session for the rest of the run)",
                "POST",
                "/api/v1/auth/login",
                auth_as=None,
                body={"email": "alice.johnson@teampulse.io", "password": PASSWORD},
                test=[status(200), save("employeeToken", "pm.response.json().access_token")],
            ),
        ],
    ),
    (
        "2 · Users & teams",
        [
            req("Me", "GET", "/api/v1/users/me", test=[status(200)]),
            req(
                "Update my display name",
                "PATCH",
                "/api/v1/users/me",
                body={"full_name": "Alice Johnson"},
                test=[status(200)],
            ),
            req("Teams (any user)", "GET", "/api/v1/teams", test=[status(200)]),
            req(
                "Team roster — own team manager",
                "GET",
                "/api/v1/teams/{{managerTeamId}}/members",
                auth_as="managerToken",
                test=[
                    status(200),
                    'pm.test("names and roles only", () => pm.expect(Object.keys(pm.response.json()[0]))'
                    '.to.have.members(["id","full_name","role"]));',
                ],
            ),
            req(
                "Team roster — employee → 403",
                "GET",
                "/api/v1/teams/{{managerTeamId}}/members",
                test=[status(403), problem("forbidden")],
            ),
            req(
                "Users (admin)",
                "GET",
                "/api/v1/users?role=employee&page=1&size=5",
                auth_as="adminToken",
                test=[status(200)],
            ),
            req(
                "Users — employee → 403",
                "GET",
                "/api/v1/users",
                test=[status(403), problem("insufficient_role")],
            ),
            req(
                "Create user (admin)",
                "POST",
                "/api/v1/users",
                auth_as="adminToken",
                body={
                    "email": "new.joiner.{{$timestamp}}@teampulse.io",
                    "full_name": "New Joiner",
                    "password": "Welcome123",
                    "role": "employee",
                    "team_id": "{{managerTeamId}}",
                },
                test=[status(201), save("newUserId", "pm.response.json().id")],
            ),
            req(
                "Create user — weak password → 422",
                "POST",
                "/api/v1/users",
                auth_as="adminToken",
                body={
                    "email": "weak@teampulse.io",
                    "full_name": "Weak",
                    "password": "weak",
                    "role": "employee",
                },
                test=[status(422)],
            ),
            req(
                "Update user role/team (admin)",
                "PATCH",
                "/api/v1/users/{{newUserId}}",
                auth_as="adminToken",
                body={"is_active": False},
                test=[status(200)],
            ),
        ],
    ),
    (
        "3 · Habits",
        [
            req(
                "Create private habit",
                "POST",
                "/api/v1/habits",
                body={
                    "title": "Evening stretch",
                    "category": "fitness",
                    "frequency": "daily",
                    "visibility": "private",
                },
                test=[status(201), save("privateHabitId", "pm.response.json().id")],
            ),
            req(
                "Create team-shared weekly habit",
                "POST",
                "/api/v1/habits",
                body={
                    "title": "Team lunch walk",
                    "category": "fitness",
                    "frequency": "weekly",
                    "target_per_period": 3,
                    "visibility": "team",
                    "color": "#16A34A",
                },
                test=[status(201), save("teamHabitId", "pm.response.json().id")],
            ),
            req(
                "Create habit — daily with target 3 → 422",
                "POST",
                "/api/v1/habits",
                body={"title": "Invalid", "category": "sleep", "frequency": "daily", "target_per_period": 3},
                test=[status(422)],
            ),
            req(
                "My habits (filter + search)",
                "GET",
                "/api/v1/habits?category=fitness&search=stretch",
                test=[status(200)],
            ),
            req(
                "Teammates' shared habits",
                "GET",
                "/api/v1/habits/team",
                auth_as="teammateToken",
                test=[status(200)],
            ),
            req(
                "Get team habit as teammate → 200",
                "GET",
                "/api/v1/habits/{{teamHabitId}}",
                auth_as="teammateToken",
                test=[status(200)],
            ),
            req(
                "Get PRIVATE habit as teammate → 404 (existence not leaked)",
                "GET",
                "/api/v1/habits/{{privateHabitId}}",
                auth_as="teammateToken",
                test=[status(404)],
            ),
            req(
                "Get team habit as other team → 404",
                "GET",
                "/api/v1/habits/{{teamHabitId}}",
                auth_as="otherTeamToken",
                test=[status(404)],
            ),
            req(
                "Update own habit",
                "PATCH",
                "/api/v1/habits/{{teamHabitId}}",
                body={"target_per_period": 2},
                test=[status(200)],
            ),
            req(
                "Update someone else's habit → 404",
                "PATCH",
                "/api/v1/habits/{{teamHabitId}}",
                auth_as="teammateToken",
                body={"title": "Hijacked"},
                test=[status(404)],
            ),
        ],
    ),
    (
        "4 · Activities (Event Tracking)",
        [
            req(
                "Log completion (→ outbox → activity.completed)",
                "POST",
                "/api/v1/activities",
                body={"habit_id": "{{privateHabitId}}", "value": 15, "note": "private note, never shared"},
                test=[status(201), save("activityId", "pm.response.json().id")],
            ),
            req(
                "Log same habit same day → 409",
                "POST",
                "/api/v1/activities",
                body={"habit_id": "{{privateHabitId}}"},
                test=[status(409), problem("already_logged")],
            ),
            req(
                "Log in the future → 422",
                "POST",
                "/api/v1/activities",
                body={"habit_id": "{{teamHabitId}}", "completed_on": "2099-01-01"},
                test=[status(422), problem("invalid_date")],
            ),
            req(
                "Log teammate's habit → 404",
                "POST",
                "/api/v1/activities",
                auth_as="teammateToken",
                body={"habit_id": "{{teamHabitId}}"},
                test=[status(404)],
            ),
            req(
                "Log unknown habit → 404",
                "POST",
                "/api/v1/activities",
                body={"habit_id": str(uuid.UUID(int=1))},
                test=[status(404)],
            ),
            req(
                "My history (date range)",
                "GET",
                "/api/v1/activities?from=2026-01-01&page=1&size=10",
                test=[status(200)],
            ),
        ],
    ),
    (
        "5 · Challenges & leaderboards",
        [
            req(
                "Create team challenge (manager, own team)",
                "POST",
                "/api/v1/challenges",
                auth_as="managerToken",
                body={
                    "title": "Postman Step Challenge",
                    "category": "fitness",
                    "team_id": "{{managerTeamId}}",
                    "starts_on": "{{today}}",
                    "ends_on": "{{inTwoWeeks}}",
                    "target_count": 5,
                    "description": "Created from the Postman collection",
                },
                test=[status(201), save("challengeId", "pm.response.json().id")],
            ),
            req(
                "Create challenge — employee → 403",
                "POST",
                "/api/v1/challenges",
                body={"title": "Nope", "starts_on": "{{today}}", "ends_on": "{{inTwoWeeks}}"},
                test=[status(403), problem("insufficient_role")],
            ),
            req(
                "Browse challenges (status + category filter)",
                "GET",
                "/api/v1/challenges?status=active&category=fitness",
                test=[status(200)],
            ),
            req(
                "Join (shown on leaderboard)",
                "POST",
                "/api/v1/challenges/{{challengeId}}/join",
                body={"show_on_leaderboard": True},
                test=[status(201)],
            ),
            req(
                "Join again → 409",
                "POST",
                "/api/v1/challenges/{{challengeId}}/join",
                body={},
                test=[status(409), problem("already_joined")],
            ),
            req(
                "Teammate joins anonymously",
                "POST",
                "/api/v1/challenges/{{challengeId}}/join",
                auth_as="teammateToken",
                body={"show_on_leaderboard": False},
                test=[status(201)],
            ),
            req(
                "Other team cannot see team challenge → 404",
                "GET",
                "/api/v1/challenges/{{challengeId}}",
                auth_as="otherTeamToken",
                test=[status(404)],
            ),
            req(
                "Leaderboard (opted-out = Anonymous participant)",
                "GET",
                "/api/v1/challenges/{{challengeId}}/leaderboard",
                test=[status(200)],
            ),
            req(
                "Hide me from leaderboard",
                "PATCH",
                "/api/v1/challenges/{{challengeId}}/participation",
                body={"show_on_leaderboard": False},
                test=[status(200)],
            ),
            req("Badge rules", "GET", "/api/v1/badge-rules", test=[status(200)]),
            req(
                "Upsert badge rule (admin → badge_rules.changed)",
                "PUT",
                "/api/v1/badge-rules/sleep_champion",
                auth_as="adminToken",
                body={
                    "name": "Sleep Champion",
                    "description": "10 early nights",
                    "icon": "😴",
                    "criterion": "category_completions",
                    "category": "sleep",
                    "threshold": 10,
                },
                test=[status(200)],
            ),
            req(
                "Upsert badge rule — employee → 403",
                "PUT",
                "/api/v1/badge-rules/sleep_champion",
                body={"name": "x", "criterion": "total_completions", "threshold": 1},
                test=[status(403)],
            ),
        ],
    ),
    (
        "6 · Insights (privacy-preserving analytics)",
        [
            req(
                "My insights (trend, streaks, badges)",
                "GET",
                "/api/v1/insights/me",
                test=[status(200)],
                description="Eventually consistent: the streak processor updates analytics asynchronously.",
            ),
            req("My streaks", "GET", "/api/v1/insights/me/streaks", test=[status(200)]),
            req("My badges", "GET", "/api/v1/insights/me/badges", test=[status(200)]),
            req(
                "Team insights — manager of team (k-anonymised)",
                "GET",
                "/api/v1/insights/teams/{{managerTeamId}}",
                auth_as="managerToken",
                test=[
                    status(200),
                    'pm.test("no member ids/names", () => '
                    'pm.expect(pm.response.text()).to.not.include("full_name"));',
                ],
            ),
            req(
                "Team insights — employee → 403",
                "GET",
                "/api/v1/insights/teams/{{managerTeamId}}",
                test=[status(403), problem("not_your_team")],
            ),
            req(
                "Org insights (admin)",
                "GET",
                "/api/v1/insights/org",
                auth_as="adminToken",
                test=[status(200)],
            ),
            req(
                "Range too long → 422",
                "GET",
                "/api/v1/insights/me?from=2025-01-01&to=2026-01-01",
                test=[status(422), problem("invalid_range")],
            ),
        ],
    ),
    (
        "7 · Notifications",
        [
            req(
                "My notifications",
                "GET",
                "/api/v1/notifications?page=1&size=20",
                test=[
                    status(200),
                    "const items = pm.response.json().items; "
                    'if (items.length) pm.collectionVariables.set("notificationId", items[0].id);',
                ],
            ),
            req("Unread count", "GET", "/api/v1/notifications/unread-count", test=[status(200)]),
            req("Mark one read", "POST", "/api/v1/notifications/{{notificationId}}/read", test=[status(200)]),
            req("Mark all read", "POST", "/api/v1/notifications/read-all", test=[status(200)]),
            req("Get reminder preferences", "GET", "/api/v1/notifications/preferences", test=[status(200)]),
            req(
                "Update reminder preferences",
                "PUT",
                "/api/v1/notifications/preferences",
                body={
                    "reminders_enabled": True,
                    "reminder_hour": 18,
                    "timezone": "Asia/Kolkata",
                    "email_enabled": True,
                },
                test=[status(200)],
            ),
            req(
                "Preferences — unknown timezone → 422",
                "PUT",
                "/api/v1/notifications/preferences",
                body={
                    "reminders_enabled": True,
                    "reminder_hour": 18,
                    "timezone": "Mars/Base",
                    "email_enabled": False,
                },
                test=[status(422)],
            ),
        ],
    ),
    (
        "8 · Security & cross-cutting failures",
        [
            req(
                "No token → 401 (rejected at the gateway)",
                "GET",
                "/api/v1/habits",
                auth_as=None,
                test=[status(401), problem("missing_token")],
            ),
            req(
                "Tampered token → 401",
                "GET",
                "/api/v1/habits",
                auth_as="tamperedToken",
                test=[status(401), problem("invalid_token")],
            ),
            req(
                "/internal endpoints are not routable → 404",
                "POST",
                "/api/v1/notifications/internal/events",
                body={},
                test=[status(404)],
            ),
            req("Unknown route → 404 problem+json", "GET", "/api/v1/does-not-exist", test=[status(404)]),
            req(
                "Correlation id is echoed (X-Request-ID)",
                "GET",
                "/api/v1/users/me",
                headers=[{"key": "X-Request-ID", "value": "postman-trace-123"}],
                test=[
                    status(200),
                    'pm.test("echoed", () => pm.expect(pm.response.headers.get("X-Request-ID"))'
                    '.to.eql("postman-trace-123"));',
                ],
            ),
            req(
                "Security headers present",
                "GET",
                "/api/v1/users/me",
                test=[
                    'pm.test("nosniff", () => pm.expect(pm.response.headers.get("X-Content-Type-Options")).to.eql("nosniff"));',
                    'pm.test("rate-limit headers", () => pm.expect(pm.response.headers.has("X-RateLimit-Remaining")).to.be.true);',
                ],
            ),
            req("Archive habit (cleanup)", "DELETE", "/api/v1/habits/{{teamHabitId}}", test=[status(204)]),
            req(
                "Logout (revoke refresh token)",
                "POST",
                "/api/v1/auth/logout",
                body={"refresh_token": "{{employeeRefreshRotated}}"},
                test=[status(204)],
            ),
        ],
    ),
]

prerequest = [
    "const d = new Date(); const iso = x => x.toISOString().slice(0, 10);",
    'pm.collectionVariables.set("today", iso(d));',
    'const later = new Date(d.getTime() + 14 * 86400000); pm.collectionVariables.set("inTwoWeeks", iso(later));',
    'pm.collectionVariables.set("tamperedToken", (pm.collectionVariables.get("employeeToken") || "x.y.z") + "tampered");',
]

collection = {
    "info": {
        "_postman_id": "6f1d6a8e-3c5b-4f7e-9a51-7f0b6d2c9e11",
        "name": "TeamPulse API",
        "description": "All TeamPulse endpoints through the API gateway — success and failure scenarios. "
        "Run top-to-bottom (Runner/Newman). Demo password for every seeded user: TeamPulse@2026.",
        "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
    },
    "event": [{"listen": "prerequest", "script": {"type": "text/javascript", "exec": prerequest}}],
    "variable": [
        {"key": k, "value": ""}
        for k in (
            "employeeToken",
            "employeeRefresh",
            "employeeRefreshRotated",
            "teammateToken",
            "otherTeamToken",
            "managerToken",
            "adminToken",
            "employeeTeamId",
            "managerTeamId",
            "newUserId",
            "privateHabitId",
            "teamHabitId",
            "activityId",
            "challengeId",
            "notificationId",
            "today",
            "inTwoWeeks",
            "tamperedToken",
        )
    ],
    "item": [{"name": name, "item": items} for name, items in folders],
}
environment = {
    "id": "2b9b7c1e-6d3f-4d6a-8c7e-0f5e9a1b2c3d",
    "name": "TeamPulse — local",
    "values": [{"key": "baseUrl", "value": "http://localhost:8000", "enabled": True}],
    "_postman_variable_scope": "environment",
}
OUT.mkdir(exist_ok=True)
(OUT / "TeamPulse.postman_collection.json").write_text(
    json.dumps(collection, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
)
(OUT / "TeamPulse.local.postman_environment.json").write_text(
    json.dumps(environment, indent=2) + "\n", encoding="utf-8"
)
print(f"{sum(len(i) for _, i in folders)} requests in {len(folders)} folders → {OUT}")
