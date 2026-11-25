-- Database-per-service bootstrap for Amazon RDS for PostgreSQL 16.
-- Run ONCE as the RDS master user from a host inside the VPC (e.g. CloudShell VPC environment):
--
--   psql "host=<RDS_ENDPOINT> port=5432 dbname=postgres user=postgres sslmode=require" \
--        -v identity_pw="$IDENTITY_PW"  -v habits_pw="$HABITS_PW" \
--        -v event_tracking_pw="$EVENT_TRACKING_PW" -v challenges_pw="$CHALLENGES_PW" \
--        -v notifications_pw="$NOTIFICATIONS_PW" -f bootstrap.sql
--
-- Each service gets its own database and its own login that owns only that database, so a compromised
-- service cannot read another service's tables (least privilege at the data tier).
\set ON_ERROR_STOP on

CREATE ROLE identity_svc       LOGIN PASSWORD :'identity_pw';
CREATE ROLE habits_svc         LOGIN PASSWORD :'habits_pw';
CREATE ROLE event_tracking_svc LOGIN PASSWORD :'event_tracking_pw';
CREATE ROLE challenges_svc     LOGIN PASSWORD :'challenges_pw';
CREATE ROLE notifications_svc  LOGIN PASSWORD :'notifications_pw';

-- PostgreSQL 16: the RDS master must be able to SET ROLE to a role before creating a database it owns.
GRANT identity_svc, habits_svc, event_tracking_svc, challenges_svc, notifications_svc TO CURRENT_USER;

CREATE DATABASE identity       OWNER identity_svc;
CREATE DATABASE habits         OWNER habits_svc;
CREATE DATABASE event_tracking OWNER event_tracking_svc;
CREATE DATABASE challenges     OWNER challenges_svc;
CREATE DATABASE notifications  OWNER notifications_svc;

REVOKE ALL ON DATABASE identity, habits, event_tracking, challenges, notifications FROM PUBLIC;

\echo 'Done: 5 databases, 5 least-privileged service logins.'
