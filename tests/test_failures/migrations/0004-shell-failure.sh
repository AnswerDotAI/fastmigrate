#!/bin/sh
# Migration that will fail with a non-zero exit code

DB_PATH="$1"

echo "This shell script migration is intentionally failing with exit code 2"
exit 2