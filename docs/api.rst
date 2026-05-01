API Documentation
====================


.. autoclass:: miggy.state::State
.. autoclass:: miggy.migrator::SchemaMigrator
    :members: sql, rename_index, create_table, drop_table
    :member-order: bysource

Migrate operations
++++++++++++++++++

.. autoclass:: miggy.operations::MigrateOperation
    :members: state_forwards, database_forwards
    :member-order: bysource
.. autoclass:: miggy.operations::RunPython
.. autoclass:: miggy.operations::RunSql
.. autoclass:: miggy.operations::CreateModel
.. autoclass:: miggy.operations::RemoveModel
.. autoclass:: miggy.operations::AddIndex
.. autoclass:: miggy.operations::DropIndex    
.. autoclass:: miggy.operations::RenameTable
.. autoclass:: miggy.operations::AddFields
.. autoclass:: miggy.operations::ChangeFields
.. autoclass:: miggy.operations::RemoveFields
.. autoclass:: miggy.operations::RenameField

Migrator
++++++++++++++++++
.. autoclass:: miggy.migrator::Migrator
    :members: add_operation,python,sql,create_model,remove_model,add_fields,change_fields,remove_fields,rename_field,rename_table,add_index,drop_index
    :member-order: bysource
