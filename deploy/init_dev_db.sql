-- Grants for one application database.
-- Roles are cluster-wide and are created once by init_dev_db.sh, so this file
-- only grants, and is re-run whenever a database is recreated.
GRANT CONNECT ON DATABASE :app_db TO :migrator_user;
ALTER SCHEMA public OWNER TO :migrator_user;
GRANT USAGE, CREATE ON SCHEMA public TO :migrator_user;

GRANT CONNECT ON DATABASE :app_db TO :app_user;
GRANT USAGE ON SCHEMA public TO :app_user;

ALTER DEFAULT PRIVILEGES FOR ROLE :migrator_user IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO :app_user;
ALTER DEFAULT PRIVILEGES FOR ROLE :migrator_user IN SCHEMA public
  GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO :app_user;
