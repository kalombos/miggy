API Documentation
====================


.. autoclass:: miggy.migrator::State
.. autoclass:: miggy.migrator::SchemaMigrator
    :members: sql, rename_index, create_table, drop_table
    :member-order: bysource

Migrate operations
++++++++++++++++++

.. autoclass:: miggy.migrator::MigrateOperation
    :members: state_forwards, database_forwards
    :member-order: bysource
.. autoclass:: miggy.migrator::RunPython
.. autoclass:: miggy.migrator::RunSql
.. autoclass:: miggy.migrator::CreateModel
.. autoclass:: miggy.migrator::RemoveModel
.. autoclass:: miggy.migrator::AddIndex
.. autoclass:: miggy.migrator::DropIndex    
.. autoclass:: miggy.migrator::RenameTable
