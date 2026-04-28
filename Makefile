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
