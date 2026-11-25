# Setup guide — run TeamPulse locally with Docker Compose

One command starts the whole system: 7 microservices, the streak processor, the web app, PostgreSQL,
RabbitMQ, DynamoDB Local, Consul and Jaeger.

## 1. What you need

| Tool | Check it works |
|---|---|
| Docker Desktop (Windows / macOS) or Docker Engine with the Compose plugin (Linux) | `docker compose version` |
| Git | `git --version` |

Give Docker at least **6 GB of memory** (*Docker Desktop → Settings → Resources*) and keep about
**5 GB of disk** free.

These ports must be free on your machine:

| Port | Used by |
|---|---|
| 8080 | web app |
| 8000 | API gateway (and Swagger) |
| 5432 | PostgreSQL |
| 5672, 15672 | RabbitMQ (broker, web UI) |
| 8500 | Consul UI |
| 8001 | DynamoDB Local |
| 16686, 4318 | Jaeger (UI, trace collector) |

## 2. Get the code

```bash
git clone <repository-url> teampulse
cd teampulse
```

## 3. Settings (optional)

The defaults work as they are. To change them, copy the example file and edit it:

```bash
cp .env.example .env
```

| Variable | Default | Meaning |
|---|---|---|
| `POSTGRES_PASSWORD` | `postgres-local` | PostgreSQL admin password |
| `SERVICE_DB_PASSWORD` | `teampulse-local` | password of each service's own database login |
| `JWT_PRIVATE_KEY` | empty | RSA key for signing tokens; empty = generated on first start and kept in a volume |
| `TAG` | `latest` | image tag |

## 4. Build and start

```bash
docker compose up --build -d
```

The first build downloads base images and builds 9 images, so it takes several minutes. Later starts
take seconds. Services start in the right order by themselves: PostgreSQL and RabbitMQ first, then
identity-service (it creates the demo users), then the other services, the gateway and the web app.

## 5. Check that it is running

```bash
docker compose ps
```

Every container should show **running** and, where it has a health check, **(healthy)**.
`dynamodb-init` shows **exited (0)**; that is expected (it only creates the analytics table).

Then open http://localhost:8000/health/services. Every service should be `up`.

## 6. Load demo data (recommended)

The demo users already exist. This adds three weeks of activity, challenges and leaderboards, so the
dashboards and charts have something to show:

```bash
docker compose run --rm seed
```

## 7. Open the app

| URL | What |
|---|---|
| http://localhost:8080 | **TeamPulse web app** |
| http://localhost:8000/docs | Swagger UI for every service (pick one at the top right) |
| http://localhost:15672 | RabbitMQ (user `guest`, password `guest`): queues and messages |
| http://localhost:8500 | Consul: registered services and their health |
| http://localhost:16686 | Jaeger: one request traced across services |

Sign in with any demo account. The password is `TeamPulse@2026` for all of them:

| Role | Email |
|---|---|
| Employee | `alice.johnson@teampulse.io` |
| Manager | `maya.patel@teampulse.io` |
| Admin | `admin@teampulse.io` |

The login page also lists every demo account; click one to fill the form.

## 8. Everyday commands

| Task | Command |
|---|---|
| Follow the logs of one service | `docker compose logs -f gateway` |
| Restart one service | `docker compose restart habit-service` |
| Rebuild after a code change | `docker compose up --build -d` |
| Stop everything (keep data) | `docker compose down` |
| Stop and delete all data | `docker compose down -v` |

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| `port is already allocated` | Another program uses that port (for example `scripts/run_local.py`). Stop it, or change the left-hand number of that port in `docker-compose.yml`. |
| A service keeps restarting | `docker compose logs <service>` shows why. Usually it waited too long for PostgreSQL; run `docker compose up -d` again. |
| Login fails after you changed `SERVICE_DB_PASSWORD` | PostgreSQL keeps the old password in its volume. Run `docker compose down -v`, then start again. |
| The web app says "A dependent service is temporarily unavailable" | A service is still starting. Wait a few seconds and check http://localhost:8000/health/services. |
| Build is slow or runs out of memory | Raise Docker's memory to 6 GB or more. |

## Without Docker

You can also run everything as plain processes (SQLite instead of PostgreSQL, HTTP calls instead of
RabbitMQ). See [Quick start](../README.md#quick-start) in the README.
