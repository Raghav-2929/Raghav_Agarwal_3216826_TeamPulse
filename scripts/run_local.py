"""Run the whole TeamPulse backend locally with ZERO infrastructure (no Docker needed).

    uv run python scripts/run_local.py            # start all 8 processes
    uv run python scripts/run_local.py --reset    # wipe local data first

* Each service gets its own SQLite database (database-per-service).
* Events use the ``direct`` driver: the publisher POSTs to each subscriber's ``/internal/events``,
  mirroring the EventBridge rules → targets wiring used in AWS (see ``EVENT_ROUTES`` below).
* The streak processor runs as a small worker hosting the same code as the AWS Lambda.
* Gateway: http://localhost:8000  (Swagger for every service: http://localhost:8000/docs)
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("TEAMPULSE_DATA_DIR", Path.home() / ".teampulse" / "data"))

SERVICES = [  # name, module, port  (identity first: everyone fetches its JWKS)
    ("identity-service", "identity_service.main", 8001),
    ("habit-service", "habit_service.main", 8002),
    ("challenge-service", "challenge_service.main", 8003),
    ("event-tracking-service", "event_tracking_service.main", 8004),
    ("insight-service", "insight_service.main", 8005),
    ("notification-service", "notification_service.main", 8006),
    ("streak-processor", "streak_processor.main", 8007),
    ("gateway", "gateway.main", 8000),
]
URL = {name: f"http://localhost:{port}" for name, _, port in SERVICES}


def inbox(service: str) -> str:
    return f"{URL[service]}/internal/events"


# The local equivalent of the EventBridge rules in AWS (docs/aws-deployment-guide.md): type → subscribers.
EVENT_ROUTES = {
    "user.registered": [inbox("notification-service")],
    "user.updated": [inbox("notification-service"), inbox("habit-service")],
    "activity.completed": [inbox("streak-processor"), inbox("notification-service")],
    "badge_rules.changed": [inbox("streak-processor")],
    "progress.updated": [inbox("challenge-service")],
    "streak.milestone": [inbox("notification-service")],
    "badge.awarded": [inbox("notification-service")],
    "challenge.*": [inbox("notification-service")],
}
COLORS = ["\033[36m", "\033[32m", "\033[33m", "\033[35m", "\033[34m", "\033[91m", "\033[96m", "\033[92m"]


def base_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "ENVIRONMENT": "local",
            "LOG_FORMAT": os.environ.get("LOG_FORMAT", "console"),
            "LOG_LEVEL": os.environ.get("LOG_LEVEL", "INFO"),
            "DATA_DIR": str(DATA_DIR),
            "EVENT_BUS_DRIVER": "direct",
            "EVENT_ROUTES": json.dumps(EVENT_ROUTES),
            "INTERNAL_TOKEN": secrets.token_urlsafe(24),
            "JWT_JWKS_URL": f"{URL['identity-service']}/.well-known/jwks.json",
            "CORS_ORIGINS": "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173",
            "ANALYTICS_STORE_DRIVER": "sql",
            "ANALYTICS_DATABASE_URL": f"sqlite+aiosqlite:///{(DATA_DIR / 'analytics.db').as_posix()}",
            "HABIT_SERVICE_URL": URL["habit-service"],
            "ACTIVITY_BACKFILL_DAYS": "30",  # generous locally so the demo seeder can build history
            "LOGIN_RATE_LIMIT_PER_MINUTE": "120",
            "REMINDER_INTERVAL_SECONDS": "300",
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    for name in ("identity", "habit", "challenge", "event_tracking", "insight", "notification"):
        env[f"{name.upper()}_SERVICE_URL"] = URL[f"{name.replace('_', '-')}-service"]
    return env


def pump(proc: subprocess.Popen[str], label: str) -> None:
    assert proc.stdout
    for line in proc.stdout:
        sys.stdout.write(f"{label} {line}")


def wait_healthy(name: str, timeout: float = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{URL[name]}/health/live", timeout=2) as resp:  # noqa: S310 - localhost
                if resp.status == 200:
                    return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> None:
    # Windows uses cp1252 when output goes to a file or pipe; the banner has "→", which would crash
    # this script after start-up and stop every service. Always write UTF-8 instead.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--reset", action="store_true", help="delete local databases before starting")
    args = parser.parse_args()
    if args.reset and DATA_DIR.exists():
        shutil.rmtree(DATA_DIR)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    env = base_env()
    procs: list[subprocess.Popen[str]] = []

    def stop_all() -> None:
        for proc in procs:
            if proc.poll() is None:
                proc.terminate()
        for proc in procs:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    def shutdown(*_: object) -> None:
        stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    try:
        run(env, procs)
    finally:
        stop_all()  # also after an unexpected error, so no service is left running in the background


def run(env: dict[str, str], procs: list[subprocess.Popen[str]]) -> None:
    width = max(len(n) for n, _, _ in SERVICES)
    for i, (name, module, port) in enumerate(SERVICES):
        service_env = {**env, "SERVICE_NAME": name, "PORT": str(port)}
        proc = subprocess.Popen(  # noqa: S603 - fixed argv
            [
                sys.executable,
                "-m",
                "uvicorn",
                f"{module}:create_app",
                "--factory",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-access-log",
            ],
            cwd=ROOT,
            env=service_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        procs.append(proc)
        threading.Thread(
            target=pump, args=(proc, f"{COLORS[i % len(COLORS)]}{name:<{width}}\033[0m |"), daemon=True
        ).start()
        if name == "identity-service" and not wait_healthy(name):
            print("identity-service failed to start", file=sys.stderr)
            break

    ok = all(wait_healthy(name) for name, _, _ in SERVICES)
    print("\n" + ("=" * 72))
    print(f" TeamPulse backend {'is UP' if ok else 'started with errors'}   (data: {DATA_DIR})")
    print("  Gateway       http://localhost:8000      Swagger UI  http://localhost:8000/docs")
    print("  Health        http://localhost:8000/health/services")
    print("  Seed demo     uv run python scripts/seed_demo.py")
    print("  Frontend      cd frontend/web && npm run dev  →  http://localhost:5173")
    print("=" * 72 + "\n")

    while True:
        time.sleep(1)
        for (name, _, _), proc in zip(SERVICES, procs, strict=False):
            if proc.poll() is not None:
                print(f"{name} exited with code {proc.returncode}; stopping everything.", file=sys.stderr)
                return  # main() stops the other services


if __name__ == "__main__":
    main()
