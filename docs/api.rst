API Documentation
====================


Operations
++++++++++

.. autoclass:: miggy.migrator::State
.. autoclass:: miggy.migrator::SchemaMigrator
    :members: sql, rename_index, create_table, drop_table
    :member-order: bysource

.. autoclass:: miggy.migrator::MigrateOperation
    :members: state_forwards, database_forwards
    :member-order: bysource

.. autoclass:: miggy.migrator::RunPython