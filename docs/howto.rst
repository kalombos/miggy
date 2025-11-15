How-To Guides
====================


How to start with an existing database schema
----------------------------------------------



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

* Delete all migration files.
* Run **miggy makemigrations**.
* Review and adjust the generated migrations if necessary.
* Run **miggy migrate --fake**.