-- Run once as a PostgreSQL superuser (or the RDS master user) on the existing server:
--   psql -h <host> -U postgres -v owner_pw=... -v app_pw=... -f setup-db.sql
-- sdtreasury owns the schema (migrations). sdt_app is what the platform connects as:
-- not owner and without BYPASSRLS, so tenant isolation (Row-Level Security) applies.
CREATE ROLE sdtreasury LOGIN PASSWORD :'owner_pw';
CREATE ROLE sdt_app LOGIN PASSWORD :'app_pw';
CREATE DATABASE sdtreasury OWNER sdtreasury;
REVOKE ALL ON DATABASE sdtreasury FROM PUBLIC;
GRANT CONNECT ON DATABASE sdtreasury TO sdt_app;
