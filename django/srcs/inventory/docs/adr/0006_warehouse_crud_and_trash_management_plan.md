# Warehouse CRUD & Trash Management Plan

This plan outlines the implementation of a full-featured Warehouse management system, including Soft-Delete (Trash) and Restore capabilities, following the established architectural patterns of the Catalog module.

## User Review Required

> [!IMPORTANT]
> **Safety Logic**: A Warehouse CANNOT be deleted if it has any historical `Stock` records (even if balance is 0), as this preserves audit integrity. 
> 
> **Trash Access**: The "Trash" view will be accessible via a specific URL to allow restoration of accidentally deleted warehouses that do not yet have history.

## Proposed Changes

### 1. Form Layer
#### [NEW] [inventory/forms/warehouse_form.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/forms/warehouse_form.py)
- Implement `WarehouseForm` for `name`, `code`, `status`, and `note`.

### 2. Service Layer Refinement
#### [MODIFY] [inventory/services/warehouse_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/services/warehouse_service.py)
- [ADD] `list_deleted()` method to return soft-deleted records.
- [MODIFY] Ensure `restore()` resets audit fields (`deleted_at`, `deleted_by`) correctly.

### 3. View Layer
#### [MODIFY] [inventory/views/warehouse_views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/views/warehouse_views.py)
- Implement:
    - `WarehouseListView`: Active warehouse overview.
    - `WarehouseTrashListView`: Soft-deleted ledger.
    - `WarehouseCreateView`: Creation via `WarehouseService.create`.
    - `WarehouseUpdateView`: Updates via `WarehouseService.update`.
    - `WarehouseDeleteView`: Soft-deletion via `WarehouseService.soft_delete`.
    - `WarehouseRestoreView`: Restoration logic.

### 4. URL Routing
#### [MODIFY] [inventory/urls.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/urls.py)
- Map `warehouses/`, `warehouses/trash/`, `warehouses/create/`, etc.

### 5. UI/Templates (Emerald Glassmorphism)
#### [NEW] Templates in `inventory/templates/inventory/`
- **warehouse_list.html**: Main table/grid with "Trash" toggle.
- **warehouse_trash_list.html**: Ledger of deleted items with "Restore" actions.
- **warehouse_form.html**: Modal/Page form for creation/edit.
- **warehouse_confirm_delete.html**: Specific warning for warehouse deletion.

## Open Questions
- *None.*

## Verification Plan

### Automated Tests
- Run `pytest inventory/tests/` (existing tests already check service logic, we will check view status codes).

### Manual Verification
- Navigate to Inventory -> Warehouses.
- Create a new warehouse "North Hub".
- Delete "North Hub".
- Open Trash, verify it exists there.
- Restore "North Hub" and verify it returns to the active list.
