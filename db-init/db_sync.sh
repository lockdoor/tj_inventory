#!/bin/sh
set -e

if [ "$REFRESH_DB_DEV" != "true" ] && [ "$REFRESH_DB_DEV" != "1" ]; then
  echo "ℹ️ REFRESH_DB_DEV is not set to 'true' or '1'. Skipping database sync from production."
  exit 0
fi

echo "⏳ Installing required tools (sshpass, openssh, postgresql-client)..."
apk add --no-cache sshpass openssh-client postgresql-client

echo "🔄 Connecting to production server ($PROD_SSH_HOST) via SSH on port ${PROD_SSH_PORT:-22} to locate docker..."
DOCKER_CMD=$(sshpass -p "$PROD_SSH_PASSWORD" ssh -p "${PROD_SSH_PORT:-22}" -o StrictHostKeyChecking=no "$PROD_SSH_USER@$PROD_SSH_HOST" \
  "for p in /usr/bin/docker /usr/local/bin/docker /snap/bin/docker /bin/docker; do if [ -x \$p ]; then echo \$p; exit 0; fi; done; which docker || echo 'docker'")
DOCKER_CMD=$(echo "$DOCKER_CMD" | tr -d '\r' | tail -n 1)
echo "📌 Remote docker path resolved to: $DOCKER_CMD"

echo "📥 Dumping production database..."
sshpass -p "$PROD_SSH_PASSWORD" ssh -p "${PROD_SSH_PORT:-22}" -o StrictHostKeyChecking=no "$PROD_SSH_USER@$PROD_SSH_HOST" \
  "echo '$PROD_SSH_PASSWORD' | sudo -S $DOCKER_CMD exec -i postgres pg_dump -U $POSTGRES_USER -d $POSTGRES_DB" > /tmp/prod_dump.sql

echo "🗑️ Resetting local development database schema..."
PGPASSWORD="$POSTGRES_PASSWORD" psql -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

echo "📥 Restoring dump into local development database..."
PGPASSWORD="$POSTGRES_PASSWORD" psql -h postgres -U "$POSTGRES_USER" -d "$POSTGRES_DB" < /tmp/prod_dump.sql

echo "✅ Database synchronization completed successfully!"
