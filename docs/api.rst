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
.. autoclass:: miggy.migrator::AddFields
.. autoclass:: miggy.migrator::ChangeFields
.. autoclass:: miggy.migrator::RemoveFields
.. autoclass:: miggy.migrator::RenameField

Migrator
++++++++++++++++++
.. autoclass:: miggy.migrator::Migrator
    :members: python,sql,create_model,remove_model,add_fields,change_fields,remove_fields,rename_field,rename_table,add_index,drop_index
    :member-order: bysource
