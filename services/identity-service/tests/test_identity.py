from __future__ import annotations

import jwt

from teampulse_common.testing import flush_outbox

from .conftest import PASSWORD, auth, login


async def test_login_returns_rs256_token_verifiable_with_published_jwks(client):
    body = await login(client, "alice.johnson@teampulse.io")
    assert body["token_type"] == "bearer"
    assert body["user"]["team_name"] == "Engineering"

    jwks = (await client.get("/.well-known/jwks.json")).json()
    key = jwt.PyJWKSet.from_dict(jwks).keys[0].key
    claims = jwt.decode(
        body["access_token"], key, algorithms=["RS256"], audience="teampulse", issuer="teampulse-identity"
    )
    assert claims["role"] == "employee"
    assert claims["team_name"] == "Engineering"
    assert claims["managed_team_ids"] == []
    assert "password" not in str(claims)


async def test_manager_token_lists_managed_team(client):
    body = await login(client, "maya.patel@teampulse.io")
    claims = jwt.decode(body["access_token"], options={"verify_signature": False})
    assert claims["role"] == "manager"
    assert claims["managed_team_ids"] == [body["user"]["team_id"]]


async def test_wrong_password_and_unknown_user_are_indistinguishable(client):
    wrong = await client.post(
        "/api/v1/auth/login", json={"email": "alice.johnson@teampulse.io", "password": "nope"}
    )
    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "ghost@teampulse.io", "password": "nope"}
    )
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.headers["content-type"].startswith("application/problem+json")
    assert wrong.json()["code"] == unknown.json()["code"] == "invalid_credentials"
    assert wrong.json()["detail"] == unknown.json()["detail"]


async def test_account_locks_after_five_failures_even_with_correct_password(client):
    for _ in range(5):
        await client.post("/api/v1/auth/login", json={"email": "ben.carter@teampulse.io", "password": "bad"})
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "ben.carter@teampulse.io", "password": PASSWORD}
    )
    assert resp.status_code == 423
    assert resp.json()["code"] == "account_locked"


async def test_refresh_rotates_and_reuse_revokes_the_family(client):
    first = await login(client, "chloe.kim@teampulse.io")
    rotated = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert rotated.status_code == 200
    second = rotated.json()
    assert second["refresh_token"] != first["refresh_token"]

    replay = await client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]})
    assert replay.status_code == 401
    # Theft detection: the legitimately rotated token is revoked too.
    after = await client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]})
    assert after.status_code == 401


async def test_two_refreshes_at_the_same_moment_cannot_both_succeed(client):
    import asyncio

    tokens = await login(client, "chloe.kim@teampulse.io")
    body = {"refresh_token": tokens["refresh_token"]}
    first, second = await asyncio.gather(
        client.post("/api/v1/auth/refresh", json=body), client.post("/api/v1/auth/refresh", json=body)
    )
    # One refresh token must never turn into two valid sessions.
    assert sorted([first.status_code, second.status_code]) == [200, 401]


async def test_logout_revokes_refresh_token(client):
    tokens = await login(client, "dev.sharma@teampulse.io")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert (
        await client.post(
            "/api/v1/auth/logout", json={"refresh_token": tokens["refresh_token"]}, headers=headers
        )
    ).status_code == 204
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert resp.status_code == 401


async def test_protected_endpoint_requires_valid_bearer(client):
    assert (await client.get("/api/v1/users/me")).status_code == 401
    bad = await client.get("/api/v1/users/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert bad.status_code == 401
    assert bad.json()["code"] == "invalid_token"


async def test_me_and_profile_update_emit_user_updated_event(client, bus):
    headers = await auth(client, "emma.davis@teampulse.io")
    me = (await client.get("/api/v1/users/me", headers=headers)).json()
    assert me["email"] == "emma.davis@teampulse.io"
    resp = await client.patch("/api/v1/users/me", json={"full_name": "Emma D."}, headers=headers)
    assert resp.json()["full_name"] == "Emma D."
    await flush_outbox(client.app)
    updated = bus.of_type("user.updated")
    assert updated[-1].data["display_name"] == "Emma D."


async def test_seed_publishes_user_registered_events_via_outbox(client, bus):
    await flush_outbox(client.app)
    assert len(bus.of_type("user.registered")) == 14


async def test_admin_creates_user_and_enforces_password_policy(client, bus):
    headers = await auth(client, "admin@teampulse.io")
    weak = await client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "new@teampulse.io", "full_name": "New Person", "password": "weak", "role": "employee"},
    )
    assert weak.status_code == 422
    assert weak.json()["errors"][0]["field"] == "password"

    ok = await client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "new@teampulse.io",
            "full_name": "New Person",
            "password": "Str0ngPass",
            "role": "employee",
        },
    )
    assert ok.status_code == 201
    dup = await client.post(
        "/api/v1/users",
        headers=headers,
        json={"email": "NEW@teampulse.io", "full_name": "Dup", "password": "Str0ngPass", "role": "employee"},
    )
    assert dup.status_code == 409
    assert dup.json()["code"] == "email_taken"
    assert (await login(client, "new@teampulse.io", "Str0ngPass"))["user"]["role"] == "employee"


async def test_employee_cannot_administer_users(client):
    headers = await auth(client, "alice.johnson@teampulse.io")
    resp = await client.get("/api/v1/users", headers=headers)
    assert resp.status_code == 403
    assert resp.json()["code"] == "insufficient_role"


async def test_admin_cannot_demote_self(client):
    tokens = await login(client, "admin@teampulse.io")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.patch(
        f"/api/v1/users/{tokens['user']['id']}", json={"role": "employee"}, headers=headers
    )
    assert resp.status_code == 400


async def test_manager_sees_only_own_team_roster(client):
    maya = await login(client, "maya.patel@teampulse.io")
    headers = {"Authorization": f"Bearer {maya['access_token']}"}
    teams = (await client.get("/api/v1/teams", headers=headers)).json()
    by_name = {t["name"]: t for t in teams}
    assert by_name["Engineering"]["manager_name"] == "Maya Patel"
    assert by_name["Engineering"]["member_count"] == 5

    own = await client.get(f"/api/v1/teams/{by_name['Engineering']['id']}/members", headers=headers)
    assert own.status_code == 200
    assert set(own.json()[0]) == {"id", "full_name", "role"}  # roster only, no wellness data
    other = await client.get(f"/api/v1/teams/{by_name['Marketing']['id']}/members", headers=headers)
    assert other.status_code == 403


async def test_change_password_signs_out_other_sessions(client):
    tokens = await login(client, "felix.wong@teampulse.io")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    resp = await client.post(
        "/api/v1/users/me/password",
        headers=headers,
        json={"current_password": PASSWORD, "new_password": "N3wSecret!"},
    )
    assert resp.status_code == 204
    assert (
        await client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    ).status_code == 401
    assert (await login(client, "felix.wong@teampulse.io", "N3wSecret!"))["user"]["full_name"] == "Felix Wong"


async def test_passwords_longer_than_bcrypt_limit_are_handled_cleanly(client):
    # bcrypt reads at most 72 bytes; longer input must give normal answers, never a 500.
    long_password = "Aa1" + "x" * 87  # 90 characters
    resp = await client.post(
        "/api/v1/auth/login", json={"email": "alice.johnson@teampulse.io", "password": long_password}
    )
    assert resp.status_code == 401
    assert resp.json()["code"] == "invalid_credentials"

    headers = await auth(client, "admin@teampulse.io")
    for password in (long_password, "Aa1" + "é" * 40):  # 43 characters but 83 bytes
        created = await client.post(
            "/api/v1/users",
            headers=headers,
            json={"email": "long@teampulse.io", "full_name": "Long Pass", "password": password},
        )
        assert created.status_code == 422
        assert created.json()["errors"][0]["field"] == "password"

    alice = await auth(client, "alice.johnson@teampulse.io")
    changed = await client.post(
        "/api/v1/users/me/password",
        headers=alice,
        json={"current_password": long_password, "new_password": "N3wSecret!"},
    )
    assert changed.status_code == 400
    assert changed.json()["code"] == "invalid_current_password"


async def test_patch_rejects_null_for_required_fields_but_allows_meaningful_nulls(client):
    headers = await auth(client, "admin@teampulse.io")
    users = (await client.get("/api/v1/users", headers=headers, params={"size": 100})).json()["items"]
    alice = next(u for u in users if u["email"] == "alice.johnson@teampulse.io")
    for field in ("full_name", "role", "is_active"):
        resp = await client.patch(f"/api/v1/users/{alice['id']}", headers=headers, json={field: None})
        assert resp.status_code == 422, field
        assert resp.json()["errors"][0]["field"] == field
    no_team = await client.patch(f"/api/v1/users/{alice['id']}", headers=headers, json={"team_id": None})
    assert no_team.status_code == 200
    assert no_team.json()["team_id"] is None

    teams = {t["name"]: t for t in (await client.get("/api/v1/teams", headers=headers)).json()}
    engineering = teams["Engineering"]["id"]
    assert (
        await client.patch(f"/api/v1/teams/{engineering}", headers=headers, json={"name": None})
    ).status_code == 422
    no_manager = await client.patch(
        f"/api/v1/teams/{engineering}", headers=headers, json={"manager_id": None}
    )
    assert no_manager.status_code == 200
    assert no_manager.json()["manager_id"] is None


async def test_renaming_a_team_to_a_taken_name_is_a_conflict(client):
    headers = await auth(client, "admin@teampulse.io")
    teams = {t["name"]: t for t in (await client.get("/api/v1/teams", headers=headers)).json()}
    engineering = teams["Engineering"]["id"]
    taken = await client.patch(f"/api/v1/teams/{engineering}", headers=headers, json={"name": "marketing"})
    assert taken.status_code == 409
    assert taken.json()["code"] == "team_name_taken"
    same = await client.patch(f"/api/v1/teams/{engineering}", headers=headers, json={"name": "ENGINEERING"})
    assert same.status_code == 200
    assert same.json()["name"] == "ENGINEERING"
