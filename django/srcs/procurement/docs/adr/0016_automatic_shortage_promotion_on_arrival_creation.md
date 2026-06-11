# ADR 0016: Automatic Shortage Promotion to Arrival Reservation on Inbound Arrival Creation

## Status
Accepted

## Context
When Sales Orders (SOs) are placed, if there is insufficient on-hand physical stock and no scheduled inbound shipments (Arrivals) to satisfy the required quantities, the system automatically registers a `Shortage` record in `PENDING` status for the unfulfilled portion. These shortages gate the Sales Orders to `DRAFT` status (as per ADR 0007).

Previously, when a procurement agent created or updated an `Arrival` (whether stand-alone or generated from a Purchase Order), there was no automatic mechanism to link outstanding shortages to the newly scheduled supply. Procurement agents had to manually resolve shortages, leading to delayed order fulfillment, manual matching errors, and a lack of real-time visibility into which shortages were covered by which incoming arrivals.

To solve this, we needed an automated pipeline to scan outstanding pending shortages upon the creation or modification of an `Arrival` document, allocate the expected incoming supply to them, and promote the matched shortages to future pre-allocations (`ArrivalReservation` records).

## Decision
We implemented an automated shortage promotion pipeline triggered during the lifecycle of an `Arrival`:

### 1. Sourcing Pipeline Integration
During `Arrival` creation (`ArrivalService.create`) or modification (`ArrivalService.update`), the system automatically invokes `ArrivalService.allocate_shortages_for_arrival(arrival, user)` inside the atomic database transaction:
- The sourcing engine queries active pending shortages for the items contained within the arrival.
- The engine filters shortages belonging to Sales Orders in `DRAFT` status (since shortage-bearing orders are held in `DRAFT` status).
- Shortages are ordered by the Sales Order expected date ascending (nearest date first) to prioritize older or more urgent customer demands.

### 2. Arrival Reservation Allocation & Promotion
For each matched shortage:
1. An `ArrivalReservation` is created linking the `ArrivalItem` to the Sales Order with the allocated quantity.
2. The corresponding `SalesAllocation` is updated: the source type changes from `SHORTAGE` to `ARRIVAL`, and it binds directly to the created `ArrivalReservation`.
3. The shortage record transitions to `Shortage.Status.PROMOTED` and saves a reference to the created `ArrivalReservation` in its `promoted_arrival_reservation` field.
4. The fully promoted shortage is then soft-deleted to keep active pending shortage lists clean while preserving historical audit logs.

### 3. Partial Shortage Allocation & Splitting
To handle situations where an incoming arrival only partially covers a pending shortage:
- The system deducts the allocated quantity from the original `Shortage` request.
- It generates a new, separate `Shortage` record marked as `PROMOTED` and soft-deleted (`is_deleted=True`), capturing the exact promoted quantity and pointing to the created `ArrivalReservation` for lineage tracking.

## Consequences

### Positive:
- **Automatic Matching & Reduced Latency**: Out-of-stock orders are automatically matched to incoming shipments as soon as supply is scheduled, reducing order processing delays.
- **Auditable Sourcing History**: Retaining the `promoted_arrival_reservation` link on the promoted shortage ensures that we can audit exactly which shortage was resolved by which incoming arrival.
- **Traceability in the UI**: Promoted shortages remain visible under the "Promoted" filter tab in shortage views and link directly to the corresponding reservation detail page.
- **Accurate Sales Order Progression**: When all shortages for an order are promoted, the order status triggers transition the Sales Order status from `DRAFT` to `PREORDER` automatically.

### Negative:
- **Additional Database Writes**: Splitting shortages on partial allocations creates extra rows in the shortage table, though these are flagged as deleted and only used for lineage/audit trails.
- **Audit Complexity**: Care must be taken when deleting or cancelling arrivals to ensure that linked promoted shortages are correctly reverted back to `PENDING` status.
