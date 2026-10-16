#!/bin/sh
# Container start: update the database first, then start the app.
# "set -e" stops the script if the migration fails, so the app never runs
# on a database with the wrong tables.
set -eu

echo "Running database migrations..."
alembic upgrade head

echo "Starting: $*"
# "exec" makes the app process 1, so it gets the stop signal from Docker.
exec "$@"
