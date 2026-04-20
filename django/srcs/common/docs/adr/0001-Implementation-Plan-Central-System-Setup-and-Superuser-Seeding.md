# Implementation Plan - Central System Setup and Superuser Seeding

The goal is to provide a single, central command to initialize the entire system from scratch. This includes creating a superuser, setting up groups/permissions, and seeding data for all modules (Catalog, Partners, Inventory).

## User Review Required

> [!CAUTION]
> **Safety Check**: This command is intended for fresh environments. If it detects existing data (e.g., existing Items or Partners), it will **stop and warn you** to prevent accidental data corruption. You must manually clear the database or use a `--force` flag (if implemented) to proceed.
>
> - A new command `python manage.py setup_system` will be created in the `common` app.
> - This command will automatically create a superuser if none exists.
> - Defaults: username `admin`, password `admin123`. You can change these via command arguments or environment variables if needed.
> - It will call all other `seed_*` commands in the correct order.

## Proposed Changes

### Common App Management Commands

#### [NEW] [setup_system.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/common/management/commands/setup_system.py)
- **Database Safety Guard**: Check `Item`, `Partner`, and `Warehouse` counts. If `> 0`, raise a `CommandError` with a warning message.
- Logic to create a superuser if `User.objects.filter(is_superuser=True).exists()` is false.
- Sequential execution of:
    1. `seed_groups` (Auth)
    2. `seed_catalog` (Categories)
    3. `seed_items_real` (with fallback logic or check for `tj_items.json`)
    4. `seed_partners` (Suppliers/Customers)
    5. `seed_warehouses` (Inventory structure)
    6. `seed_inventory_data` (Sample movements)

### Improvement to existing commands
I will slightly modify `seed_items_real.py` to be more "silent" or return a status so `setup_system` can decide whether to run the mock `seed_items` as a fallback.

## Verification Plan

### Automated Tests
- Run `python manage.py setup_system` on a clean (or existing) database.
- Verify that a superuser is created.
- Verify that all subsequent seeders were called and data is populated.

### Manual Verification
- Log in with the new superuser credentials.
- Check that Groups, Categories, Items, and Partners are all present.
