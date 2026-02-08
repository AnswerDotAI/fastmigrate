# Release Notes

## 0.5.1

- Clean up tests/style


## 0.5.0

## Enhancements

- Add support for database-independent migrations via ``migrations/config.py`` backend adapters (sync or async).
- ``run_migrations`` now delegates SQL execution and version bookkeeping to the adapter when present.


## 0.4.1

- fastship

## 0.4.0

- Add `fastmigrate_enroll_db` command to CLI
- Simplify and enhance errors messages and UI copy

## 0.3.0

### Enhancements

- Update CLI interface to use separate executables, not subcommands.
  (This is a breaking change in the CLI so I'm bumping the minor
  version number, even though we're still under major version 0. The
  API is not changed.)

## 0.2.5

### Bug fixes

- if the CLI is called with `--backup`, and the backup fails, then the
  command fails

### Enhancements

- backup operation uses SQLite's backup API, so it no longer requires
  the sqlite3 command line tool to be installed
  
- API now takes `Path` objects as well as `str` objects, which also
  enables path completion

