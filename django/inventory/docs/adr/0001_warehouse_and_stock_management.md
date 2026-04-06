# Warehouse Service and Testing Plan

This plan outlines the implementation of the `WarehouseService` in the `inventory` app and its corresponding unit tests using `pytest`, following the pattern established in the `catalog` app.

## User Review Required

> [!IMPORTANT]
> **Business Rules**:
> 1. **Deactivation**: A warehouse cannot be deactivated (`status = inactive`) if it contains any active stock balances (even in other lots).
> 2. **Soft Deletion**: A warehouse cannot be deleted if it has any associated stock records (regardless of balance) to maintain historical integrity.

## Proposed Changes

### 1. Inventory App Services
#### [NEW] [django/inventory/services/warehouse_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/services/warehouse_service.py)
- [ADD] `WarehouseService` class with `@staticmethod` methods.
- [ADD] `get_active_queryset()`: Exclude soft-deleted records.
- [ADD] `create()`: Standardized creation with audit info.
- [ADD] `update()`: Handle status changes and basic fields with validation.
- [ADD] `soft_delete()` / `restore()`: Standard soft-delete logic from `AuditableMixin`.

### 2. Unit Testing
#### [NEW] [django/tests/inventory/services/test_warehouse_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/tests/inventory/services/test_warehouse_service.py)
- [ADD] Pytest class for `WarehouseService` tests.
- [ADD] Test cases:
    - Successful creation and update.
    - Blocking deactivation if stock exists.
    - Blocking deletion if stock exists.
    - Successful soft deletion and restoration.

## Open Questions
- *None at this stage.*

## Verification Plan

### Automated Tests
- Run `pytest django/tests/inventory/services/test_warehouse_service.py`.
- Run full suite `pytest django/tests/inventory/` to ensure no side effects.
