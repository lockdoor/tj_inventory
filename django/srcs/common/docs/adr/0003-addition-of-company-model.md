# ADR 0003: Addition of Company Model for Multi-Company Management

**Status:** Accepted  
**Date:** 2026-06-30  

## Context

As the TJ Inventory system expands, there is a requirement to support multi-company operations, beginning with a new `petty_cash` module. Previously, company entities were only implicitly defined in environment variables and settings configurations (specifically `COMPANY_WAREHOUSE_CODES`). This made it impossible to associate transactions, accounts, and partners with actual database-backed company records.

To support true multi-tenancy and multi-company cash flow tracking, we need a centralized database representation of internal legal entities (companies) that can be referenced across various app contexts.

## Decision

We introduced a concrete `Company` model in the `common` app.

1. **Placement in `common` app**: 
   The `Company` model was placed in the `common` app (within a newly structured `common/models/` package). Since the `common` app is the foundational layer of the codebase (housing mixins like `AuditableMixin` and `StatusMixin`), other context apps can import and reference `Company` without introducing circular dependencies.

2. **Model Design**:
   The `Company` model inherits from `AuditableMixin` and `StatusMixin` to inherit audit logging, soft-deletion capabilities, and status management. It defines fields including:
   - `name`: Display name.
   - `code`: Unique identifier (e.g. `TJ`, `TJG`).
   - `express_database_name`: Mapped name matching the legacy Express ERP database (e.g. `TJ69`, `JINTAN68`).
   - `tax_id`, `address`, `phone`, `email`, and `note`.

3. **Codebase Modularization**:
   To keep the `common` models maintainable, we split `common/models.py` into a package directory (`common/models/`) containing:
   - `sample_item.py` (concrete classes purely for testing abstract mixins)
   - `company.py` (the `Company` model definition)
   - `__init__.py` (re-exporting classes for external exposure)

## Consequences

### Positive
* **Single Source of Truth**: Internal company configurations are now managed as active database models, which can be modified directly via the Django admin panel.
* **Extensibility**: Future modules like `petty_cash` can immediately link to `common.Company` using foreign key relations.
* **Maintainability**: Splitting model files ensures a modular, readable codebase structure as the application grows.

### Negative
* **Migration Dependency**: Any context app referencing the `Company` model must declare a migration dependency on `common`'s schema migrations.
