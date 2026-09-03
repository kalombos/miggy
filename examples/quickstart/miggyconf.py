from app.models import BaseModel, database

# Database connection. Can be a DSN string, peewee.Database, or peewee.Proxy object. Required.
DATABASE = database

# list[str]. Model names to ignore when detecting changes.
# Use Model._meta.name to get the model name.
IGNORE = [BaseModel._meta.name]

# str | None. If set, run SET search_path TO 'schema' for each migration.
# This allows migrations to be applied to a different schema.
SCHEMA = None

# str. Name of the table used to store migration history.
MIGRATE_TABLE = "migratehistory"

# str | pathilib.Path. Path to the migration directory.
MIGRATE_DIR = "migrations"
