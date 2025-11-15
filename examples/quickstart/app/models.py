import peewee as pw
from playhouse.postgres_ext import DateTimeTZField, PostgresqlExtDatabase

POSTGRES_DSN = "postgresql://postgres:postgres@localhost:5432/postgres"



database = PostgresqlExtDatabase(POSTGRES_DSN)


class BaseModel(pw.Model):
    created_at = DateTimeTZField(constraints=[pw.SQL("DEFAULT now()")])

    class Meta:
        database = database


class User(BaseModel):
    first_name = pw.CharField()
    last_name = pw.CharField(index=True)
    age = pw.IntegerField(null=True)

    class Meta:
        database = database