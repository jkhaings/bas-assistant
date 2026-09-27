-- Runs once, when the postgres data volume is first initialized (official
-- postgres image convention: every *.sql under docker-entrypoint-initdb.d
-- runs against POSTGRES_DB, connected as POSTGRES_USER).
--
-- Creates a second database for `make test-int`, owned by the same app user,
-- so `alembic upgrade head` behaves identically against it.
CREATE DATABASE bas_test OWNER bas_assistant;
