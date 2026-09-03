import peewee as pw
import playhouse.postgres_ext as pw_pext

# Run the migration inside a single transaction
__ATOMIC = True


def migrate(migrator, database, fake=False):
    """Write your migrations here."""

    migrator.create_model(
        name="User",
        fields={
            "created_at": pw_pext.DateTimeTZField(constraints=[pw.SQL("DEFAULT now()")]),
            "first_name": pw.CharField(),
            "last_name": pw.CharField(),
        },
        meta={},
    )


def rollback(migrator, database, fake=False):
    """Write your rollback migrations here."""

    migrator.remove_model(
        "user",
    )
