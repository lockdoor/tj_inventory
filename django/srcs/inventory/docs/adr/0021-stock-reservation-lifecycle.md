# ADR 0021: Status-Tracked Auditable Stock Reservation Lifecycle

## Status
Accepted

## Context
Previously, when a stock reservation was completed (e.g. order shipped) or manually released/cancelled, the reservation record was physically deleted (`hard-deleted`) from the database. 
This caused significant data consistency and tracing issues:
- There was no historical trail of who locked which physical lots, when they were locked, and when they were released.
- Completed order shipments lost their connection to the exact stock lot allocations that fulfilled them, making historical audits and WMS tracking extremely difficult.
- Reverting warehouse documents back to draft created duplication and double-allocation bugs because completed reservation histories could not be referenced or reactivated.

## Decision
We decided to transition the `StockReservation` model from hard physical deletion to a status-tracked, soft-deletable lifecycle utilizing `AuditableMixin` to preserve history and robust WMS traceability.

### 1. Auditable Mixin Integration
`StockReservation` now inherits from `AuditableMixin`. This automatically registers:
- Creation and modification metadata (`created_at`, `created_by`, `updated_at`, `updated_by`).
- Soft-delete status (`is_deleted`, `deleted_at`, `deleted_by`) that overrides the standard Django `.delete()` behaviour to toggle flags rather than drop rows.
- Full revision version tracking and historical data logging via `simple-history` under `HistoricalStockReservation`.

### 2. Lifecycle Status Transitions
We introduced a `status` choices field to explicitly represent the state of the reservation:
- `RESERVED` (`reserved`): Active lock on physical stock (default state).
- `COMPLETED` (`completed`): The lock was successfully fulfilled (stock was physically moved/shipped in outbound movement), preserved for traceability.
- `RELEASED` (`released`): The lock was manually cancelled or released by a planner or system event, which also toggles `is_deleted=True` (soft-delete).

### 3. Active Constraints on Availability
All dynamic checks, capacity allocations, and stock lot synchings (`reserved_qty` on `Stock`) must strictly filter active holdings by querying:
`is_deleted=False` AND `status=StockReservation.ReservationStatus.RESERVED`.
Completed and released holds are preserved in the database but are completely excluded from active stock reservation sums.

### 4. Sourcing & Reversion Reactivation
When picking slips are generated via outbound movements, only active reservations are packaged. When a completed movement is reverted back to draft, the system looks up the existing reservation with `status=COMPLETED` and reactivates it back to `RESERVED` status. This preserves the original database integrity and prevents duplicate `SalesAllocation` mapping rows.

## Consequences
- **Positive**: Full operational auditing. We can easily run hold reports to track reservation histories, creators, completers, and exact lots.
- **Positive**: Fixes critical double-allocation display errors by reactivating existing reservations in-place on WMS document reversions.
- **Positive**: Maintains perfect consistency in cross-module trace links (WMS, Sales, and Procurement) across historical shipments.
- **Negative**: Queries checking active stock holds must consistently apply status and soft-delete filters.
