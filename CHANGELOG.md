# Release Notes

## 0.2.5

### Bug fixes

- if the CLI is called with `--backup`, and the backup fails, then the
  command fails

### Enhancements

- backup operation uses SQLite's backup API, so it no longer requires
  the sqlite3 command line tool to be installed
  
  
