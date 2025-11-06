"""Peewee migrations."""


def migrate(migrator, database, **kwargs):
    """Write your migrations here.

    > Model = migrator.orm['name']

    > migrator.sql(sql)
    > migrator.python(func, *args, **kwargs)
    > migrator.create_model(Model)
    > migrator.store_model(Model)
    > migrator.remove_model(Model, cascade=True)
    > migrator.add_fields(Model, **fields)
    > migrator.change_fields(Model, **fields)
    > migrator.remove_fields(Model, *field_names, cascade=True)
    > migrator.rename_field(Model, old_field_name, new_field_name)
    > migrator.rename_table(Model, new_table_name)
    > migrator.add_index(Model, *col_names, unique=False)
    > migrator.drop_index(Model, index_name)
    > migrator.add_not_null(Model, field_name)
    > migrator.drop_not_null(Model, field_name)
    > migrator.add_default(Model, field_name, default)

    """

    def save_person(schema_migrator, state):
        Person = state["person"]
        Person(
            first_name="First",
            last_name="Last",
            email="person@example.com",
        ).save()

    migrator.python(save_person)


def rollback(migrator, database, **kwargs):
    def delete_person(schema_migrator, state):
        Person = state["person"]
        Person.delete().where(Person.email == "person@example.com").execute()

    migrator.python(delete_person)
