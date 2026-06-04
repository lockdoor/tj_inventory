# ADR 0008: Optimize Allocation and Reservation to Reuse Soft-Deleted Records

## Status
Accepted (2026-06-04)

## Context
Our Django models employ soft-deletion globally via the `AuditableMixin` (by setting `is_deleted = True` and recording audit fields). 
* **Redundant Database Writes & Bloat**: Previously, when manual allocations were updated in the UI (e.g., re-allocating a stock lot or arrival item), or when allocations were reset back to automatic ("Reset to Auto"), the system would soft-delete the old manual allocations and reservations and create brand-new ones.
* **Primary Key Churn & Orphans**: Because the database default managers do not exclude soft-deleted records automatically, and the service layers previously only queried active records, re-allocating the same stock lot or arrival item resulted in duplicate allocations pointing to the same lot, one soft-deleted and one active. This led to database row bloat and unnecessary primary key churn.

## Decision
We refactored the persistence layer for both manual allocations (`save_manual_allocations`) and automatic allocations (`refresh_allocation`) to check, restore, and reuse existing soft-deleted records instead of creating duplicates.

### 1. Unified Soft-Deleted Record Mapping
* **Lookup Maps**: When manual overrides are saved or when automatic waterfall matching runs, the services load **all** allocations (both active and soft-deleted) for the order item using `order_item.allocations.all()`.
* **Safe Relation Resolution**: We build lookup dictionaries mapping `stock_id` and `arrival_item_id` to their respective allocation records. To prevent crashes, accessing the foreign keys (e.g. `alloc.physical_reservation`) is protected with `try...except` in case a related object has been physically hard-deleted.

### 2. Soft-Deleted Record Restoration & Reuse
* **In-Place Reuse**:
  - If a submitted quantity is greater than zero, and a soft-deleted allocation exists for that stock lot or arrival item, we restore it:
    ```python
    # Restore reservation (and status for stock reservations)
    reservation.restore()
    reservation.status = StockReservation.ReservationStatus.RESERVED
    reservation.save(update_fields=['status'])
    
    # Restore allocation
    existing_alloc.restore()
    ```
  - We then update the quantity in-place on the restored reservation and allocation, ensuring that the primary keys remain completely stable.
* **Audit-Safe Release**:
  - If the submitted quantity is `0` (or when the auto-allocator cleans up non-manual allocations), we release the reservation (`ReservationService.release(..., user=user)`) and soft-delete the allocation (`allocation.delete(user=user)`). This preserves history and audit fields without churning new rows.

## Consequences
* **Positive**: Minimizes database table bloat and prevents primary key IDs from climbing unnecessarily.
* **Positive**: Ensures that manual allocations and reservations keep stable IDs, enabling consistent frontend state representation and reports.
* **Positive**: Maintains a clean history and audit trail since deletion timestamps and user tracking are preserved inside soft-deleted rows.
