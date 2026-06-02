PYTHON = ./django/venv/bin/python
PIP = ./django/venv/bin/pip
MANAGE = ./django/srcs/manage.py
REQS = ./django/requirements.txt

all:
	$(PYTHON) $(MANAGE) runserver 0.0.0.0:8000

express_run:
	./express/venv/bin/python ./express/main.py

install:
	$(PIP) install -r $(REQS)

setup:
	rm -rf ./django/venv
	python3.11 -m venv ./django/venv
	$(MAKE) install

excel_migration:
	$(PYTHON) ./django/migrate/scripts/excel_migration.py

migrate_fresh:
	rm -f ./django/srcs/db.sqlite3
	$(PYTHON) $(MANAGE) makemigrations
	$(PYTHON) $(MANAGE) migrate
	$(PYTHON) $(MANAGE) setup_system

venv:
	@echo "To activate the virtual environment, run:"
	@echo "source ./django/venv/bin/activate"

# docker zone
up:
	docker compose up -d

down:
	docker compose down

rebuild:
	$(MAKE) down
	docker compose up --build -d

rebuild_fresh:
	docker compose down -v
	docker compose up --build --force-recreate -d

dk_migrate:
	docker exec -it django python manage.py migrate

dk_setup:
	docker exec -it django python manage.py setup_system

dk_migrate_fresh:
	docker exec -it django python manage.py migrate
	docker exec -it django python manage.py setup_system

# Database migration (for NAS migration)
backup_db:
	@echo "Backing up database..."
	docker exec -t postgres pg_dump -U tjglobal -d tjglobal | gzip > database_backup.sql.gz
	@echo "✓ Backup created: database_backup.sql.gz"

restore_db:
	@echo "Restoring database from backup..."
	gunzip < database_backup.sql.gz | docker exec -i postgres psql -U tjglobal -d tjglobal
	@echo "✓ Database restored successfully."

# We must exclude contenttypes and auth.permission because Django creates these automatically, 
# and including them would cause duplicate key errors later.
# get datadump.json to local develop environment ./django/migrate/data/datadump.json
# delete old sqlite db and reset database in local develop environment
# cd django/srcs
# rm -f db.sqlite3
# python manage.py migrate
# python manage.py loaddata ../migrate/data/datadump.json
# python manage.py seed_groups

dump_json:
	docker exec -it django python manage.py dumpdata --exclude auth.permission --exclude contenttypes > datadump.json

# Delete Database 
dk_db_drop:
	@echo "Dropping and recreating database 'tjglobal'..."
	docker exec -it postgres psql -U tjglobal -d postgres -c "REVOKE CONNECT ON DATABASE tjglobal FROM public;"
	docker exec -it postgres psql -U tjglobal -d postgres -c "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = 'tjglobal' AND pid <> pg_backend_pid();"
	docker exec -it postgres psql -U tjglobal -d postgres -c "DROP DATABASE IF EXISTS tjglobal;"
	docker exec -it postgres psql -U tjglobal -d postgres -c "CREATE DATABASE tjglobal;"
	@echo "✓ Database 'tjglobal' reset successfully."

dk_reset:
	$(MAKE) dk_db_drop
	$(MAKE) dk_migrate
	$(MAKE) dk_setup
