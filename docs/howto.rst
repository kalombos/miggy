How-To Guides
====================


How to start with an existing database schema
----------------------------------------------

If you already have a project with an existing schema, you can easily integrate Miggy:

1. Run **miggy makemigrations**.
2. Review and adjust the generated migration if necessary.
3. **Run miggy migrate --fake** to mark the migration as applied.


How to merge migrations
-----------------------
Over time, the number of migration files in a project may grow, which can gradually increase the time 
required to generate new migrations. In such cases, you can merge all migrations into a single file 
using the **miggy merge**. command. This command merge all existing migrations into one 
and updates the **migratehistory** table accordingly to reflect the merged state. 

Unfortunately, using this command is not always possible, 
as projects often contain custom migrations—whether they add data or 
are written with custom SQL because Miggy’s capabilities may be limited. 
In such cases, migrations can be merged manually:

1. Delete all migration files.
2. Run **miggy makemigrations**.
3. Review and adjust the generated migration if necessary.
4. Manually update the migratehistory table. It should contain only the migration created in step 2