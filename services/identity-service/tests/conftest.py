from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest

from identity_service.config import Settings
from identity_service.main import create_app
from teampulse_common.events import InMemoryEventBus
from teampulse_common.testing import running_client, sqlite_url

PASSWORD = "TeamPulse@2026"


@pytest.fixture
def bus() -> InMemoryEventBus:
    return InMemoryEventBus()


@pytest.fixture
async def client(tmp_path, bus) -> AsyncIterator[httpx.AsyncClient]:
    settings = Settings(
        _env_file=None,
        environment="test",
        database_url=sqlite_url(tmp_path),
        data_dir=str(tmp_path),
        log_level="WARNING",
        demo_password=PASSWORD,
    )
    app = create_app(settings, publisher=bus, bcrypt_rounds=4)
    async with running_client(app) as c:
        c.app = app  # type: ignore[attr-defined]
        yield c


async def login(client: httpx.AsyncClient, email: str, password: str = PASSWORD) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()


async def auth(client: httpx.AsyncClient, email: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {(await login(client, email))['access_token']}"}
