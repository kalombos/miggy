class Migration:
    atomic = True

    @staticmethod
    def migrate(migrator, database, fake=False) -> None:
        pass

    @staticmethod
    def rollback(migrator, database, fake=False) -> None:
        pass
