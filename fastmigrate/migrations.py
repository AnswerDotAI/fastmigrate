from pathlib import Path
from apswutils import Database, Table  # type: ignore

def recreate_table(db_path:Path,         # db path
                   table_name:str,      # name of table to update by re-creating
                   new_column_defs:str  # updated column definitions
                   ) -> None:
    """Update a table by recreating it and copying existing data.

    For updates which cannot be achieved with `Table.transform()`,
    this helper implements the "other kinds of table schema changes"
    pattern dictated in Sec 7 of
    https://sqlite.org/lang_altertable.html.

    `new_column_defs` must be a comma-separated list of COLUMN-DEFs
    (and optionally TABLE-CONTSTRAINTs), containing at least all the
    columns appearing in `table.columns`.

    For details: https://sqlite.org/syntax/column-def.html and
    https://sqlite.org/syntax/table-constraint.html
    """
    db = Database(db_path)
    table = db[table_name]
    col_names = ','.join(c.name for c in table.columns)
    stmt = f"""BEGIN TRANSACTION;
PRAGMA foreign_keys=OFF;

CREATE TABLE {table.name}_new (
{new_column_defs}
);

INSERT INTO {table.name}_new ({col_names})
    SELECT {col_names}
    FROM {table.name};

DROP TABLE {table.name};

ALTER TABLE {table.name}_new RENAME TO {table.name};
    
PRAGMA foreign_key_check;
COMMIT;
PRAGMA foreign_keys=ON;"""
    db.execute(stmt)
