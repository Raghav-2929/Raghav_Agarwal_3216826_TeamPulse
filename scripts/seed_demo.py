"""Populate a running TeamPulse stack with realistic demo activity — through the public API only, so
the whole event flow (outbox → bus → streak processor → analytics / challenges / notifications) runs.

    uv run python scripts/seed_demo.py [--gateway http://localhost:8000] [--days 21]

Idempotent per user: anyone who already has habits is skipped.
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import UTC, datetime, timedelta

import httpx

PASSWORD = "TeamPulse@2026"
EMPLOYEES = [
    "maya.patel",
    "omar.haddad",
    "priya.nair",
    "alice.johnson",
    "ben.carter",
    "chloe.kim",
    "dev.sharma",
    "emma.davis",
    "felix.wong",
    "grace.lee",
    "henry.lopez",
    "isla.brown",
    "jack.wilson",
]
HABITS = [
    {"title": "Morning walk", "category": "fitness", "visibility": "team", "color": "#16A34A"},
    {"title": "10-minute meditation", "category": "mindfulness", "visibility": "private", "color": "#7C3AED"},
    {"title": "Drink 8 glasses of water", "category": "hydration", "visibility": "team", "color": "#0284C7"},
    {"title": "Lights out by 11pm", "category": "sleep", "visibility": "private", "color": "#4338CA"},
    {"title": "Read 20 pages", "category": "learning", "visibility": "team", "color": "#D97706"},
    {"title": "Eat a proper lunch", "category": "nutrition", "visibility": "private", "color": "#DC2626"},
]


class Api:
    def __init__(self, base: str) -> None:
        self.http = httpx.Client(base_url=base, timeout=30)

    def login(self, email: str) -> dict[str, str]:
        resp = self.http.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
        resp.raise_for_status()
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    def call(self, method: str, path: str, headers: dict[str, str], **kwargs) -> httpx.Response:  # type: ignore[no-untyped-def]
        resp = self.http.request(method, path, headers=headers, **kwargs)
        if resp.status_code >= 400 and resp.status_code != 409:
            raise RuntimeError(f"{method} {path} → {resp.status_code}: {resp.text[:300]}")
        return resp


def main() -> None:
    # Windows uses cp1252 when output goes to a file or pipe; the progress lines use "✓" and "→".
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser()
    parser.add_argument("--gateway", default="http://localhost:8000")
    parser.add_argument(
        "--days", type=int, default=21, help="days of history to back-fill (≤ ACTIVITY_BACKFILL_DAYS)"
    )
    args = parser.parse_args()
    api = Api(args.gateway)
    rng = random.Random(2026)  # noqa: S311 - deterministic demo data, not crypto
    today = datetime.now(UTC).date()

    # Challenges first (they start today, so today's activities count towards them).
    admin = api.login("admin@teampulse.io")
    maya = api.login("maya.patel@teampulse.io")
    existing = api.call("GET", "/api/v1/challenges", admin).json()["total"]
    if not existing:
        me = api.call("GET", "/api/v1/users/me", maya).json()
        api.call(
            "POST",
            "/api/v1/challenges",
            admin,
            json={  # admins may backdate ≤ 14 days
                "title": "November Hydration Hero",
                "category": "hydration",
                "target_count": 10,
                "description": "Org-wide: log your water intake every day this month. "
                "Which team stays best hydrated?",
                "starts_on": (today - timedelta(days=14)).isoformat(),
                "ends_on": (today + timedelta(days=14)).isoformat(),
            },
        )
        api.call(
            "POST",
            "/api/v1/challenges",
            admin,
            json={
                "title": "Two-Week Reading Sprint",
                "category": "learning",
                "target_count": 8,
                "description": "Org-wide: 20 pages a day. Knowledge compounds!",
                "starts_on": (today - timedelta(days=10)).isoformat(),
                "ends_on": (today + timedelta(days=4)).isoformat(),
            },
        )
        api.call(
            "POST",
            "/api/v1/challenges",
            maya,
            json={
                "title": "Engineering Step-Up",
                "category": "fitness",
                "target_count": 12,
                "team_id": me["team_id"],
                "description": "Engineering only: a walk, run or ride every day for three weeks.",
                "starts_on": today.isoformat(),
                "ends_on": (today + timedelta(days=20)).isoformat(),
            },
        )
        api.call(
            "POST",
            "/api/v1/challenges",
            admin,
            json={
                "title": "Mindful December",
                "category": "mindfulness",
                "target_count": 15,
                "description": "Ten quiet minutes a day through December.",
                "starts_on": (today + timedelta(days=10)).isoformat(),
                "ends_on": (today + timedelta(days=40)).isoformat(),
            },
        )
        print("✓ challenges created")

    for handle in EMPLOYEES:
        headers = api.login(f"{handle}@teampulse.io")
        if api.call("GET", "/api/v1/habits", headers).json()["total"]:
            print(f"· {handle}: already seeded, skipping")
            continue
        consistency = rng.uniform(0.55, 0.95)  # each person has their own rhythm
        habits = [
            api.call("POST", "/api/v1/habits", headers, json={**h, "frequency": "daily"}).json()
            for h in rng.sample(HABITS, k=3)
        ]
        for challenge in api.call("GET", "/api/v1/challenges?status=active", headers).json()["items"]:
            if rng.random() < 0.85:
                api.call(
                    "POST",
                    f"/api/v1/challenges/{challenge['id']}/join",
                    headers,
                    json={"show_on_leaderboard": rng.random() < 0.8},
                )
        logged = 0
        for offset in range(args.days, -1, -1):
            day = today - timedelta(days=offset)
            for habit in habits:
                if rng.random() < consistency:
                    api.call(
                        "POST",
                        "/api/v1/activities",
                        headers,
                        json={
                            "habit_id": habit["id"],
                            "completed_on": day.isoformat(),
                            "value": round(rng.uniform(1, 3), 1),
                        },
                    )
                    logged += 1
        print(f"✓ {handle}: {len(habits)} habits, {logged} activities")
    print("Done. Sign in at http://localhost:5173 (password for every demo user: TeamPulse@2026)")


if __name__ == "__main__":
    main()
