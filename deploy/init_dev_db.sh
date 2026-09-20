#!/bin/bash
# Initialise the development cluster: two databases in one Postgres container.
#
#   $POSTGRES_DB   the scratch database the agent works in
#   $DEV_SHOW_DB   the showcase database `harness dev reset --db show` recreates
#
# Roles are cluster-wide, so they are created once here and the grants are then
# applied to each database.
set -e

psql_admin() {
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" "$@"
}

psql_admin <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$MIGRATOR_DB_USER') THEN
    CREATE ROLE "$MIGRATOR_DB_USER" LOGIN PASSWORD '$MIGRATOR_DB_PASSWORD';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$APP_DB_USER') THEN
    CREATE ROLE "$APP_DB_USER" LOGIN PASSWORD '$APP_DB_PASSWORD';
  END IF;
END
\$\$;
SQL

if ! psql_admin -tAc "SELECT 1 FROM pg_database WHERE datname = '$DEV_SHOW_DB'" | grep -q 1; then
  psql_admin -c "CREATE DATABASE \"$DEV_SHOW_DB\" OWNER \"$POSTGRES_USER\""
fi

for db in "$POSTGRES_DB" "$DEV_SHOW_DB"; do
  psql -v ON_ERROR_STOP=1 \
    -v migrator_user="$MIGRATOR_DB_USER" \
    -v app_user="$APP_DB_USER" \
    -v app_db="$db" \
    --username "$POSTGRES_USER" --dbname "$db" \
    -f /opt/init_dev_db.sql
done
