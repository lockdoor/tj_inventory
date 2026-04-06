# Inventory Movement Service (Draft Phase) Plan

This plan outlines the implementation of the `MovementService` to handle the lifecycle of inventory movement documents while they are in the `draft` state.

## User Review Required

> [!IMPORTANT]
> **Status Override**: I will override the `status` field in the `InventoryMovement` model to use `draft` and `completed` (as per the ERD) instead of the default `active/inactive` from `StatusMixin`.
> **Safety Lock**: The service will enforce a rule that only documents in `draft` status can be modified. Once a document is `completed`, it becomes immutable for these service methods.

## Proposed Changes

### 1. Model Updates
#### [MODIFY] [inventory/models/movement.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/models/movement.py)
- [ADD] `Status` TextChoices with `DRAFT` and `COMPLETED`.
- [MODIFY] `status` field to use these new choices (default: `DRAFT`).

### 2. Inventory App Services
#### [MODIFY] [inventory/services/__init__.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/services/__init__.py)
- [ADD] Export `MovementService`.

#### [NEW] [inventory/services/movement_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/services/movement_service.py)
- [ADD] `MovementService` class with `@staticmethod` methods.
- [ADD] `create_draft(...)`: Standardized document initialization.
- [ADD] `add_item(...)`, `update_item(...)`, `remove_item(...)`: Item line management.
- [ADD] `add_attachment(...)`, `remove_attachment(...)`: File management.
- [ADD] `soft_delete_draft(...)`: Deleting the entire draft document.

### 3. Unit Testing
#### [NEW] [tests/inventory/services/test_movement_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/tests/inventory/services/test_movement_service.py)
- [ADD] Pytest class for `MovementService`.
- [ADD] Test cases:
    - Successful draft creation.
    - Adding/Updating items in draft.
    - Blocking modifications if document is `completed`.
    - Attachment handling (using `SimpleUploadedFile`).

## Open Questions
- *None at this stage.*

## Verification Plan

### Automated Tests
- Run `makemigrations inventory` and `migrate inventory` (for status change).
- Run `pytest django/tests/inventory/services/test_movement_service.py`.
