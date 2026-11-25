#!/bin/sh
# Database-per-service on one PostgreSQL server: each service gets its own database and its own
# least-privileged login that owns only that database (mirrors the RDS bootstrap task in AWS).
set -eu

for pair in identity:identity_svc habits:habit_svc event_tracking:event_tracking_svc \
            challenges:challenge_svc notifications:notification_svc; do
  db="${pair%%:*}"
  user="${pair##*:}"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-SQL
    CREATE ROLE ${user} LOGIN PASSWORD '${SERVICE_DB_PASSWORD}';
    CREATE DATABASE ${db} OWNER ${user};
    REVOKE ALL ON DATABASE ${db} FROM PUBLIC;
SQL
  echo "created database ${db} owned by ${user}"
done
