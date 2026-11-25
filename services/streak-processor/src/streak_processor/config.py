from __future__ import annotations

from functools import lru_cache

from teampulse_common.settings import AnalyticsSettings


class Settings(AnalyticsSettings):
    service_name: str = "streak-processor"


@lru_cache
def get_settings() -> Settings:
    return Settings()
