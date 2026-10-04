#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 \
     -v migrator_user="$MIGRATOR_DB_USER" \
     -v app_user="$APP_DB_USER" \
     -v app_db="$POSTGRES_DB" \
     --username "$POSTGRES_USER" \
     --dbname "$POSTGRES_DB" \
     -f /opt/init_db.sql
