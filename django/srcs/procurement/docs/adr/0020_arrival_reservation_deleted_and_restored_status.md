# ADR 0020: Arrival Reservation Model Soft-Delete and Status Alignment

## Status
Accepted (2026-06-17)

## Context
In the procurement module, pre-allocations of expected arrivals are tracked using `ArrivalReservation` records. These reservations can transition to various statuses (`RESERVED`, `CANCELLED`, `PROMOTED`).
Previously, arrival reservations were soft-deleted (by setting `is_deleted = True`) during two different flows:
1. **Cancellation / Release**: When a reservation is manually cancelled or released by the user or the system (such as when an arrival is deleted/cancelled or when remaining quantities are reverted), it enters `CANCELLED` status and is soft-deleted.
2. **Promotion**: When the arrival is received, the pre-allocation is promoted to a physical stock reservation, entering `PROMOTED` status, and was also soft-deleted (`is_deleted = True`).

Similar to the Shortage model (see [ADR 0019](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/docs/adr/0019_shortage_deleted_and_restored_status.md)), this posed a problem where administrators purging/hard-deleting soft-deleted records would delete historical promoted records. Promoted reservations need to remain active (`is_deleted = False`) as part of the lineage history, while cancelled/soft-deleted reservations should have `is_deleted = True`.

## Decision
We aligned the `ArrivalReservation` model's soft-delete flag (`is_deleted`) to strictly represent the `CANCELLED` status:
* **Promoted reservations remain active**: Both full and split promoted reservations now retain `is_deleted = False` and transition to `status = 'promoted'`.
* **Cancelled reservations are soft-deleted**: Reservations that are manually soft-deleted, released, or cancelled now have `is_deleted = True` and `status = 'cancelled'`.

To enforce this alignment cleanly across all database operations, we implemented the following mechanisms:

### 1. Model-Level Hooks (`ArrivalReservation` model)
* **`delete()` Override**: Automatically transitions the status to `CANCELLED` before performing the soft-delete (`super().delete()`).
* **`restore()` Override**: Automatically checks if status is `CANCELLED`. If so, resets the status to `RESERVED` before performing the restore. Other statuses (e.g., `PROMOTED`) are preserved.
* **`save()` Override**: Synchronizes status and soft-delete states:
  - If `is_deleted` is `True`, enforces `status = 'cancelled'`.
  - If `status` is `CANCELLED`, enforces `is_deleted = True`.
  - In both paths, populates `deleted_at` and `deleted_by` if they are not already set.

### 2. Sourcing & Promotion Logic Updates
* **Promotion to Stock**: In `ArrivalService.finalize_from_movement`, removed the `arr_res.delete()` call for full promotions (transitioning to `PROMOTED` status with `is_deleted = False`), and created split promoted records with `is_deleted = False`.
* **Status-Aware Queries**: Modified queries and checks in `ArrivalService` (e.g., checking available quantities, reverting to shortages on cancellation or short receipts) and `ArrivalItem` (in validation and deletion hooks) to filter by `status = ArrivalReservation.ReservationStatus.RESERVED` explicitly. This prevents already-promoted reservations from being re-processed or reverted.

### 3. View Queryset Gating
* **`ArrivalReservationListView`**: Modified `get_queryset` to query active records (`is_deleted = False`).
* **`ArrivalReservationDetailView`**: Modified `get_queryset` to query `ArrivalReservation.objects.all()` so details of soft-deleted cancelled reservations can be retrieved and viewed.

## Consequences
* **Positive**: Administrators can safely purge soft-deleted records (`is_deleted = True`) without losing promoted reservation history.
* **Positive**: Strict model-level overrides guarantee that `is_deleted` and `status = 'cancelled'` will never drift out of sync.
* **Positive**: Promoted reservations remain visible on list and detail pages as non-deleted records.
