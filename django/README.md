# TJ Inventory - Django Backend Application

This is the core Django backend application for the Inventory, Procurement, Sales, and Petty Cash ERP system.

---

## 📂 Project Structure

The project code is located inside the [srcs/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/) directory and is organized into functional Django apps:

*   **[app/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/app/)**: Main project settings, routing, and WSGI/ASGI entrypoints.
*   **[catalog/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/catalog/)**: Handles item catalogs, categories, units, and inventory listings.
*   **[common/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/common/)**: Common core utilities, bilingual naming support, and the `Individual` profile.
*   **[dashboard/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/dashboard/)**: Dashboard views and KPIs tailored to roles like Stock Controller and Warehouse Admin.
*   **[inventory/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/inventory/)**: Manages warehouse locations, physical stock balances, stock movements, and reservation records.
*   **[partners/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/partners/)**: Handles business partners (customers and suppliers).
*   **[procurement/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/procurement/)**: Manages purchase orders, materials shortages, and purchase arrivals.
*   **[sales/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/sales/)**: Manages sales orders and handles manual/automatic inventory allocation (using stock & arrivals).
*   **[petty_cash/](file:///home/jintanexp/win-work/tj_inventory/django/srcs/petty_cash/)**: Manages petty cash accounts, payments, and integrations.

---

## 🛠️ Local Development Setup

To run the Django application locally outside of Docker (on your WSL host):

### 1. Create and Activate Virtual Environment
```bash
# Navigate to the django folder
cd django

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Database Selection Behavior
The database configuration in [settings.py](file:///home/jintanexp/win-work/tj_inventory/django/srcs/app/settings.py) dynamically shifts depending on the environment:
*   **Inside Docker (Development/Production):** Uses PostgreSQL as configured in the `.env` file.
*   **Outside Docker (Local Terminal/Testing):** Automatically falls back to **SQLite** (`django/srcs/db.sqlite3`). This prevents local shell operations from trying to hit external PostgreSQL hosts.

To initialize your local SQLite database:
```bash
cd srcs
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

---

## 🧪 Testing Guide

The project uses `pytest` and `pytest-django` for automated test suites. 

### Database Behavior during Tests
*   When tests are executed, a **temporary in-memory SQLite database** is created automatically.
*   All migrations are run on the temporary database from scratch.
*   The database is **completely deleted/discarded** after the tests finish, ensuring your development database is never modified.

### How to Run Tests

#### Method A: From the `django/srcs/` Directory (Recommended)
Navigating to the source folder allows pytest to automatically find the config [pytest.ini](file:///home/jintanexp/win-work/tj_inventory/django/srcs/pytest.ini) file:
```bash
cd django/srcs

# Run all tests
../venv/bin/pytest

# Run only files you have modified (via pytest-picked)
../venv/bin/pytest --picked

# Run a specific test module
../venv/bin/pytest tests/common/test_individual.py

# Run a specific test function
../venv/bin/pytest tests/common/test_individual.py -k "test_individual_creation"
```

#### Method B: From the Project Root Directory
If you want to run tests without changing directories, you must pass the path to the configuration file using the `-c` flag:
```bash
./django/venv/bin/pytest -c django/srcs/pytest.ini django/srcs
```
