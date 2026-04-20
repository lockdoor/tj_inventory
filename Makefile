PYTHON = ./django/venv/bin/python
MANAGE = ./django/srcs/manage.py

all:
	$(PYTHON) $(MANAGE) runserver 0.0.0.0:8000

migrate_fresh:
	rm -f ./django/srcs/db.sqlite3
	$(PYTHON) $(MANAGE) makemigrations
	$(PYTHON) $(MANAGE) migrate
	$(PYTHON) $(MANAGE) setup_system

venv:
	@echo "To activate the virtual environment, run:"
	@echo "source ./django/venv/bin/activate"
