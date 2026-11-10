#!/bin/sh
# Container entrypoint. With SDT_RUN_MIGRATIONS=true the schema is upgraded before the
# command starts (safe with several replicas: migrations take a PostgreSQL advisory lock).
set -e
if [ "${SDT_RUN_MIGRATIONS:-false}" = "true" ]; then
    alembic upgrade head
fi
exec "$@"
