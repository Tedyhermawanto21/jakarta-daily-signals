-- Read-only access for Looker Studio. Safe to re-run.
-- Run in the Neon SQL Editor on the production branch, database jds, as the table owner.
--
-- Create the role with SQL first, not from the Neon Console Roles page: Console roles join
-- neon_superuser. Choose your own password; it never goes into the repo.
--
--     create role looker_reader with login password '<strong-password>';
--
-- Verify afterwards with: uv run python -m jds.check_reader

revoke all on schema raw, staging, ops from looker_reader;
revoke all on all tables in schema raw, staging, ops from looker_reader;
revoke create on schema public from looker_reader;

grant usage on schema marts to looker_reader;
grant select on all tables in schema marts to looker_reader;

-- dbt recreates mart tables on every run, which drops grants on the old tables.
alter default privileges for role jds_owner in schema marts
grant select on tables to looker_reader;

alter role looker_reader set default_transaction_read_only = on;
alter role looker_reader set statement_timeout = '30s';
