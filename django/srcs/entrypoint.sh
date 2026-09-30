#!/bin/sh
set -e

echo "🔄 Running database migrations..."
python manage.py migrate --noinput

# Continue to the command (CMD) specified in the Dockerfile
exec "$@"
