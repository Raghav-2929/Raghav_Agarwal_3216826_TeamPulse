from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from gateway.main import Settings, create_app, match_route
from gateway.ratelimit import TokenBucketLimiter
from teampulse_common.testing import bearer, make_token, running_client, verifier_for_tests


class Upstreams:
    """Fake downstream services: records what the gateway forwarded."""

    def __init__(self) -> None:
        self.calls: list[httpx.Request] = []
        self.status = 200
        self.fail_connect = False
        self.problem_code: str | None = None  # answer as application/problem+json with this code

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        if self.fail_connect:
            raise httpx.ConnectError("refused", request=request)
        if request.url.path == "/health/live":
            return httpx.Response(200, json={"status": "ok"})
        if self.problem_code:
            return httpx.Response(
                self.status,
                json={"status": self.status, "code": self.problem_code},
                headers={"content-type": "application/problem+json"},
            )
        return httpx.Response(
            self.status,
            json={"host": request.url.host, "path": request.url.path},
            headers={"x-request-id": "upstream-id", "content-encoding": "identity"},
        )


@pytest.fixture
def upstreams() -> Upstreams:
    return Upstreams()


@pytest.fixture
async def client(tmp_path, upstreams) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=str(tmp_path),
        log_level="WARNING",
        identity_service_url="http://identity",
        habit_service_url="http://habit",
        challenge_service_url="http://challenge",
        event_tracking_service_url="http://events",
        insight_service_url="http://insight",
        notification_service_url="http://notification",
        login_rate_limit_per_minute=3,
        rate_limit_per_minute=600,
        max_body_bytes=1024,
    )
    app = create_app(settings, verifier=verifier_for_tests(), transport=httpx.MockTransport(upstreams))
    async with running_client(app) as c:
        yield c


TOKEN = bearer(make_token(role="employee"))


@pytest.mark.parametrize(
    ("path", "service"),
    [
        ("/api/v1/auth/login", "identity-service"),
        ("/api/v1/habits/team", "habit-service"),
        ("/api/v1/badge-rules/x", "challenge-service"),
        ("/.well-known/jwks.json", "identity-service"),
        ("/api/v1/habitsX", None),
        ("/api/v2/habits", None),
    ],
)
def test_route_matching_is_prefix_and_segment_aware(path, service):
    route = match_route(path)
    assert (route.service if route else None) == service


async def test_forwards_to_the_right_service_with_path_query_and_headers(client, upstreams):
    resp = await client.get(
        "/api/v1/habits?category=fitness",
        headers={
            **TOKEN,
            "X-Internal-Token": "spoofed",
            "X-Request-ID": "req-123",
            "X-Forwarded-For": "203.0.113.9",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"host": "habit", "path": "/api/v1/habits"}
    forwarded = upstreams.calls[-1]
    assert forwarded.url.params["category"] == "fitness"
    assert forwarded.headers["authorization"].startswith("Bearer ")
    assert "x-internal-token" not in forwarded.headers  # spoofable header stripped
    assert forwarded.headers["x-request-id"] == "req-123"  # correlation id propagated
    assert forwarded.headers["x-forwarded-for"] == "203.0.113.9"
    assert resp.headers["x-request-id"] == "req-123"  # not the upstream's
    assert "x-ratelimit-remaining" in resp.headers


async def test_edge_rejects_missing_or_invalid_tokens_without_calling_upstream(client, upstreams):
    for headers in ({}, {"Authorization": "Bearer garbage"}, bearer(make_token(token_type="refresh"))):
        resp = await client.get("/api/v1/insights/me", headers=headers)
        assert resp.status_code == 401
        assert resp.headers["content-type"].startswith("application/problem+json")
    assert upstreams.calls == []


async def test_public_auth_endpoints_need_no_token(client):
    assert (
        await client.post("/api/v1/auth/login", json={"email": "a@b.c", "password": "x"})
    ).status_code == 200


async def test_internal_and_unknown_paths_are_not_routable(client, upstreams):
    assert (await client.post("/api/v1/habits/internal/events", headers=TOKEN)).status_code == 404
    assert (await client.get("/internal/events", headers=TOKEN)).status_code == 404
    assert (await client.get("/api/v1/unknown", headers=TOKEN)).status_code == 404
    assert upstreams.calls == []


async def test_login_is_rate_limited_per_client_ip(client):
    for _ in range(3):
        assert (await client.post("/api/v1/auth/login", json={})).status_code == 200
    blocked = await client.post("/api/v1/auth/login", json={})
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) >= 1
    other_ip = await client.post("/api/v1/auth/login", json={}, headers={"X-Forwarded-For": "198.51.100.7"})
    assert other_ip.status_code == 200


async def test_login_limit_cannot_be_dodged_with_a_fake_forwarded_for(client):
    # One trusted proxy (the default): only the last X-Forwarded-For entry, written by our proxy, counts.
    for n in range(3):
        fake = {"X-Forwarded-For": f"10.0.0.{n}, 198.51.100.7"}
        assert (await client.post("/api/v1/auth/login", json={}, headers=fake)).status_code == 200
    blocked = await client.post(
        "/api/v1/auth/login", json={}, headers={"X-Forwarded-For": "10.9.9.9, 198.51.100.7"}
    )
    assert blocked.status_code == 429


def test_client_ip_uses_the_entry_written_by_our_first_proxy():
    from starlette.requests import Request

    from gateway.main import client_ip

    def request(xff: str | None) -> Request:
        headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
        return Request({"type": "http", "headers": headers, "client": ("10.1.1.1", 1234)})

    assert client_ip(request("1.1.1.1, 2.2.2.2, 3.3.3.3"), 1) == "3.3.3.3"  # nginx / ALB only
    assert client_ip(request("1.1.1.1, 2.2.2.2, 3.3.3.3"), 2) == "2.2.2.2"  # CloudFront + ALB
    assert client_ip(request("2.2.2.2"), 2) == "2.2.2.2"  # fewer entries than proxies
    assert client_ip(request("1.1.1.1"), 0) == "10.1.1.1"  # header ignored
    assert client_ip(request(None), 1) == "10.1.1.1"  # no header: TCP peer


async def test_repeated_query_keys_reach_the_service_unchanged(client, upstreams):
    resp = await client.get("/api/v1/habits?tag=a&tag=b&q=morning%20run", headers=TOKEN)
    assert resp.status_code == 200
    forwarded = upstreams.calls[-1]
    assert forwarded.url.params.get_list("tag") == ["a", "b"]
    assert forwarded.url.params["q"] == "morning run"
    plain = await client.get("/api/v1/habits", headers=TOKEN)
    assert plain.status_code == 200
    assert str(upstreams.calls[-1].url) == "http://habit/api/v1/habits"


async def test_body_size_limit(client):
    resp = await client.post("/api/v1/habits", headers=TOKEN, content=b"x" * 2048)
    assert resp.status_code == 413


async def test_large_bodies_are_refused_without_reading_them_all(client, upstreams):
    declared = await client.post(
        "/api/v1/habits", headers={**TOKEN, "Content-Length": "999999"}, content=b"x" * 10
    )
    assert declared.status_code == 413  # refused from the Content-Length header alone

    async def chunked_upload():  # no Content-Length: the gateway counts while it reads
        for _ in range(100):
            yield b"x" * 512

    streamed = await client.post("/api/v1/habits", headers=TOKEN, content=chunked_upload())
    assert streamed.status_code == 413
    assert upstreams.calls == []
    small = await client.post("/api/v1/habits", headers=TOKEN, content=b"{}")
    assert small.status_code == 200


async def test_bad_tokens_count_against_the_ip_limit(tmp_path, upstreams):
    settings = Settings(
        _env_file=None,
        environment="test",
        data_dir=str(tmp_path),
        log_level="WARNING",
        habit_service_url="http://habit",
        rate_limit_per_minute=6,  # bucket of 2
    )
    app = create_app(settings, verifier=verifier_for_tests(), transport=httpx.MockTransport(upstreams))
    async with running_client(app) as c:
        bad = {"Authorization": "Bearer garbage"}
        assert (await c.get("/api/v1/habits", headers=bad)).status_code == 401
        assert (await c.get("/api/v1/habits", headers=bad)).status_code == 401
        third = await c.get("/api/v1/habits", headers=bad)
        assert third.status_code == 429
        assert int(third.headers["retry-after"]) >= 1
    assert upstreams.calls == []


async def test_circuit_opens_after_repeated_upstream_failures_and_fails_fast(client, upstreams):
    upstreams.status = 503
    for _ in range(5):
        assert (await client.get("/api/v1/challenges", headers=TOKEN)).status_code == 503
    calls_before = len(upstreams.calls)
    fast = await client.get("/api/v1/challenges", headers=TOKEN)
    assert fast.status_code == 503
    assert "circuit open" in fast.json()["detail"]
    assert len(upstreams.calls) == calls_before  # upstream not even called
    upstreams.status = 200
    still_open = await client.get("/api/v1/challenges", headers=TOKEN)
    assert still_open.status_code == 503  # stays open until recovery timeout
    other = await client.get("/api/v1/habits", headers=TOKEN)  # breakers are per upstream
    assert other.status_code == 200

    status = (await client.get("/health/services")).json()
    assert status["services"]["challenge-service"] == "circuit_open"


async def test_dependency_outage_inside_a_service_does_not_open_its_breaker(client, upstreams):
    # Event tracking answers 503 dependency_unavailable while habit-service is down. The service
    # itself is fine, so its breaker stays closed and its other endpoints keep working.
    upstreams.status, upstreams.problem_code = 503, "dependency_unavailable"
    for _ in range(7):
        resp = await client.post("/api/v1/activities", headers=TOKEN, json={})
        assert resp.status_code == 503
        assert "circuit open" not in resp.json().get("detail", "")
    assert len([c for c in upstreams.calls if c.url.path == "/api/v1/activities"]) == 7  # all reached it

    upstreams.problem_code = None  # a plain 503 (for example "no healthy upstream") still counts
    for _ in range(5):
        await client.get("/api/v1/activities", headers=TOKEN)
    fast = await client.get("/api/v1/activities", headers=TOKEN)
    assert "circuit open" in fast.json()["detail"]


async def test_connection_errors_become_problem_503(client, upstreams):
    upstreams.fail_connect = True
    resp = await client.get("/api/v1/notifications", headers=TOKEN)
    assert resp.status_code == 503
    assert resp.json()["code"] == "dependency_unavailable"


def test_token_bucket_refills_over_time():
    now = [0.0]
    limiter = TokenBucketLimiter(60, burst=2, clock=lambda: now[0])
    assert limiter.check("k")[0]
    assert limiter.check("k")[0]
    allowed, _, retry_after = limiter.check("k")
    assert not allowed
    assert retry_after == pytest.approx(1.0)
    now[0] += 1.0
    assert limiter.check("k")[0]
