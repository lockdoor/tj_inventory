all:
	source venv/bin/activate && python ./django/manage.py runserver 0.0.0.0:8000

migrate_fresh:
	rm django/db.sqlite3
	source venv/bin/activate && python ./django/manage.py makemigrations
	source venv/bin/activate && python ./django/manage.py migrate
	source venv/bin/activate && python ./django/manage.py setup_system
