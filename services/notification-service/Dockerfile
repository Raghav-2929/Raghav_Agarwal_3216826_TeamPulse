# syntax=docker/dockerfile:1.7
# TeamPulse Notification Service — Reminders, challenge updates, milestones
# Build from the repository root:  docker build -f services/notification-service/Dockerfile -t teampulse/notification-service .

# ---------- build stage: install exactly the locked dependency set of this one service
FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY libs ./libs
COPY services ./services
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --package teampulse-notification-service

# ---------- runtime stage: slim, non-root, no build tooling, no source tree
FROM python:3.13-slim
LABEL org.opencontainers.image.title="teampulse-notification-service" \
      org.opencontainers.image.description="Reminders, challenge updates, milestones" \
      org.opencontainers.image.source="https://github.com/your-org/teampulse" \
      org.opencontainers.image.licenses="MIT"
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data && chown app:app /data
COPY --from=build --chown=app:app /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SERVICE_NAME=notification-service \
    PORT=8000 \
    DATA_DIR=/data \
    LOG_FORMAT=json
WORKDIR /app
USER 10001
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3 \
  CMD ["python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2).status == 200 else 1)"]
CMD ["uvicorn", "notification_service.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*", "--no-access-log"]
