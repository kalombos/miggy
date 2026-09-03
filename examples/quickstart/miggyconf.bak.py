from app.models import BaseModel, database

DATABASE = database

# database.allow_sync() # if you use peewee-async

IGNORE = [BaseModel._meta.name]
