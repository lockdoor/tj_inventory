# ADR 0022: Warehouse Company Reference and Express Integration Refactoring

**Status:** Accepted  
**Date:** 2026-06-30  

## Context

Previously, the mapping between internal Django warehouses (e.g. `TG001`, `TJ001`) and external legacy Express ERP databases (e.g. `TJ69`, `JINTAN68`) was stored in an environment variable setting named `COMPANY_WAREHOUSE_CODES`. 

Having this mapping hardcoded in environment configs made dynamic company and warehouse assignments difficult to manage, required container restarts for changes, and prevented database-level foreign key constraints. With the introduction of the centralized database-backed `Company` model (see `common` ADR 0003), we need to replace this settings-based configuration with proper database relations.

## Decision

We transitioned the company-to-warehouse mapping to the database and completely removed the `COMPANY_WAREHOUSE_CODES` environment configuration:

1. **Warehouse Model Updates**:
   We added a foreign key field `company` to the `Warehouse` model (in [warehouse.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/inventory/models/warehouse.py)):
   ```python
   company = models.ForeignKey(
       'common.Company',
       on_delete=models.SET_NULL,
       null=True,
       blank=True,
       related_name='warehouses',
       help_text="The company this warehouse belongs to"
   )
   ```

2. **Automated Seeding and Data Migration**:
   We created a custom data migration (`0019_auto_20260630_0938.py`) to:
   - Seed `Company` records in the database based on the historical mapping (`{"TJ69": "TG001", "JINTAN68": "TJ001"}`).
   - Retrieve or create a system migration user to satisfy the `created_by` audit logs.
   - Associate the seeded companies to their respective warehouse rows directly via the new `company` database reference.

3. **Express Service Refactoring**:
   We updated `ExpressService` to look up available companies and warehouse associations in the database via the `Company` and `Warehouse` relationship using `express_database_name` as the key.

4. **Environment Settings Removal**:
   We completely removed `COMPANY_WAREHOUSE_CODES` from settings, environment files (`.env`, `.env.example`, `secrets/django.env`, `secrets/django.env.example`), and Docker compose configurations (`compose_dev.yaml`, `compose_prd.yaml`).

## Consequences

### Positive
* **Database Constraints**: The mapping is now strictly verified at the database schema level.
* **No Code/Env Restarts**: New companies and their associated warehouses can now be mapped dynamically via the Django admin panel without modifying environment variables or restarting application containers.
* **Cleaner Configuration**: Removed a complex JSON-encoded environment variable from all configuration templates.

### Negative
* **Migration Dependency**: The `inventory` migration defining the `company` field has a strict dependency on `common`'s schema migrations.
