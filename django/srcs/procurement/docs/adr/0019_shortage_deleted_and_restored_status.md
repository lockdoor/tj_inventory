# ADR 0019: Shortage Model Soft-Delete and Status Alignment

## Status
Accepted (2026-06-17)

## Context
In the procurement module, material shortages can be transitioned to various statuses (e.g., `PENDING`, `PO_CREATED`, `PROMOTED`, `CANCELLED`).
Previously, shortage records were soft-deleted (by setting `is_deleted = True`) during two different flows:
1. **Cancellation / Release**: When a shortage is manually cancelled or released by the system, it enters `CANCELLED` status and is soft-deleted.
2. **Fulfillment / Promotion**: When a shortage is satisfied by expected arrivals, it enters `PROMOTED` status and was also soft-deleted (`is_deleted = True`).

This design posed a problem: administrators who wish to purge/hard-delete cancelled records could not distinguish them from successfully promoted ones by searching simply for `is_deleted = True`. Promoted shortages must remain available as historical/audit records (`is_deleted = False`) while cancelled/soft-deleted shortages should have `is_deleted = True`.

## Decision
We aligned the `Shortage` model's soft-delete flag (`is_deleted`) to strictly represent the `CANCELLED` status:
* **Promoted shortages remain active**: Both full and split promoted shortages now retain `is_deleted = False` and transition to `status = 'promoted'`.
* **Cancelled shortages are soft-deleted**: Shortages that are manually soft-deleted or cancelled now have `is_deleted = True` and `status = 'cancelled'`.

To enforce this alignment cleanly across all database operations, we implemented the following mechanisms:

### 1. Model-Level Hooks (`Shortage` model)
* **`delete()` Override**: Automatically transitions the status to `CANCELLED` before performing the soft-delete (`super().delete()`).
* **`restore()` Override**: Automatically checks if status is `CANCELLED`. If so, resets the status to `PENDING` before performing the restore. Other statuses (e.g., `PROMOTED`) are preserved.
* **`save()` Override**: Synchronizes status and soft-delete states:
  - If `is_deleted` is `True`, enforces `status = 'cancelled'`.
  - If `status` is `CANCELLED`, enforces `is_deleted = True`.
  - In both paths, populates `deleted_at` and `deleted_by` if they are not already set.

### 2. Sourcing Promotion Logic (`ArrivalService`)
* **Full Promotion**: Removed the `shortage.delete()` call, transitioning status to `PROMOTED` and saving the link.
* **Split Promotion**: Creates the split shortage record in `PROMOTED` status with `is_deleted = False`.

### 3. View Queryset Gating
* **`ShortageListView`**: Modified `get_queryset` to query `is_deleted = True` only when explicitly filtering for `status = 'cancelled'`. Otherwise, it queries active records (`is_deleted = False`).
* **`ShortageDetailView`**: Modified `get_queryset` to query `Shortage.objects.all()` so details of soft-deleted cancelled shortages can be retrieved and viewed.

## Consequences
* **Positive**: Administrators can safely purge soft-deleted records (`is_deleted = True`) without losing promoted shortage history.
* **Positive**: Strict model-level overrides guarantee that `is_deleted` and `status = 'cancelled'` will never drift out of sync.
* **Positive**: Promoted shortages remain visible on list and detail pages as non-deleted records.
