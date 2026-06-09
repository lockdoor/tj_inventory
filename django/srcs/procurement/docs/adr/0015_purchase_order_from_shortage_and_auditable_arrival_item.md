# ADR 0015: Purchase Order Creation from Material Shortages & Auditable ArrivalItem

## Status
Accepted

## Context

### 1. Purchase Order Creation from Material Shortages
When material shortages are flagged (e.g., due to incoming sales orders or stock discrepancies), they are tracked as pending shortages. Previously, procurement agents had to manually track these shortages on side channels and type in Purchase Order (PO) headers and lines from scratch. There was no integration between shortages and POs, leading to errors, duplicate orders, and a lack of visibility. We needed a workflow to allow users to select pending shortages directly from the Shortages list and generate a pre-populated PO to cover them, while maintaining a clear status link between the shortage and the generated PO.

### 2. Auditable ArrivalItem
The `ArrivalItem` model represents individual line items within an incoming shipment (`Arrival`). Initially, `ArrivalItem` was declared as a subclass of `models.Model`. Because of this, it lacked important compliance, audit, and locking capabilities—specifically, tracking creation and update metadata (`created_at`, `created_by`, `updated_at`, `updated_by`), soft-deletion, and optimistic locking (`version`). To align with other critical entities in the system, `ArrivalItem` needed to inherit from the core `AuditableMixin` class.

## Decision

We implemented the following design and architectural changes:

### 1. Shortage-to-PO Generation Pipeline
- **Checkbox Selection**: Introduced row selection checkboxes in the "Pending" tab of the Shortages list.
- **Dedicated View & Form**: Created a custom view `PurchaseOrderCreateFromShortageView` and template `purchase_order_from_shortage_form.html`. This page groups selected shortages by item and pre-populates item lines.
- **Sourcing Decision Support**: The form displays the exact shortage sum per item in the line item row. It contains a packaging calculator that suggests the package units required (e.g. `Suggest: 2.00 Box` when shortage is 15 pieces and 1 box contains 10 pieces) and highlights whether the input order quantity is sufficient (green) or insufficient (orange/red).
- **PO-Shortage Status Lifecycle**: When the PO is created, linked shortages transition to `PO_CREATED`. If the PO is later soft-deleted or transitioned to `CANCELLED`, all linked shortages are reverted to `PENDING` and their `purchase_order` reference is cleared.

### 2. Auditing and Traceability on ArrivalItem
- **AuditableMixin Inheritance**: Changed the class signature to `class ArrivalItem(AuditableMixin)`. This automatically registers fields like `created_at`, `created_by`, `updated_at`, `updated_by`, `is_deleted`, `deleted_at`, `deleted_by`, `version`, and historical logs via `HistoricalRecords`.
- **Service Integration**: Updated `ArrivalService.sync_items` to accept the acting `user` object. We updated the creation, update, and soft-delete methods within the service to pass `user` down to model saves and deletions, ensuring the audit logs are correctly populated.
- **Migration & Test Updates**:
  - Generated database migration `procurement.0014_arrivalitem_created_at_arrivalitem_created_by_and_more`. Since `created_by` is a non-nullable ForeignKey to `User`, a default user ID (`1` representing the admin) was set for existing rows.
  - Updated all `ArrivalItem.objects.create` calls in the test suite to pass `created_by=user` (or `test_user`/`admin_user`) to satisfy database constraints.

## Consequences

### Positive:
- **Streamlined Sourcing**: Stock controllers can convert pending shortages into purchase orders with a single click, eliminating manual entry and reducing human error.
- **Better Purchasing Decisions**: Displaying shortages directly inside the line item section and providing instant packaging calculations ensures that optimal packaging configurations are ordered.
- **Full Traceability**: `ArrivalItem` is now fully trackable. We can see who created, modified, or soft-deleted shipment items, preventing audit gaps.
- **Robust locking**: Optimistic locking checks on `ArrivalItem` prevent concurrency issues when multiple operators handle the same shipment.

### Negative:
- **Test Verbosity**: Unit tests must now provide acting user parameters when creating `ArrivalItem` records, increasing setup boilerplate slightly.
- **Data Migration Care**: Adding non-nullable audit fields on existing tables requires providing default values in migration files.
