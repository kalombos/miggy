import peewee as pw

# Run the migration inside a single transaction
__ATOMIC = True


def migrate(migrator, database, fake=False):
    """Write your migrations here."""

    migrator.add_field(
        model_name="user",
        name="age",
        field=pw.IntegerField(null=True),
    )

    migrator.alter_field(
        model_name="user",
        name="last_name",
        field=pw.CharField(index=True),
    )


def rollback(migrator, database, fake=False):
    """Write your rollback migrations here."""

    migrator.remove_field(
        model_name="user",
        name="age",
    )

    migrator.alter_field(
        model_name="user",
        name="last_name",
        field=pw.CharField(),
    )
