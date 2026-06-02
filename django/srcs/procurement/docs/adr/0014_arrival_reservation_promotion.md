# ADR 0014: Inbound Arrival Receipt & Reservation Promotion with Lineage Tracking

## Status
Accepted

## Context
When Sales Orders are created, if no physical stock is available on-hand but scheduled inbound shipments (Arrivals) are expected to land on or before the order's expected fulfillment date, the Smart Sourcing engine automatically pre-allocates future cargo. This creates an `ArrivalReservation` (future pre-allocation) and a `SalesAllocation(source_type=ARRIVAL)`.

When the physical goods arrive at the warehouse, the receiving team registers the cargo and completes the inbound `InventoryMovement` (status becomes `COMPLETED`). At this moment:
1. The future pre-allocation hold must transition into an active, physical `StockReservation` hold.
2. If this conversion only references the `Arrival` as the primary parent, daily warehouse picking operations, shipping slips, and WMS allocations lose direct reference to the ultimate customer order (the `Sales Order`). Resolving who the stock belongs to would require deep, complex, and slow SQL joins (`StockReservation` -> `ArrivalItem` -> `ArrivalReservation` -> `SalesOrderItem` -> `SalesOrder`), leading to operational confusion and query performance bottlenecks.

## Decision
We implemented an automated "Promotion" logic for future allocations to transition pre-allocated arrivals into physical stock locks upon receipt with the following architectural decisions:

### 1. Direct Parent Referencing
The promoted `StockReservation` points **directly** to the ultimate customer order (`reference_no` and `sales_item` referencing the `SalesOrder` and `SalesOrderItem` respectively). This keeps all daily warehouse picking slips, picking queues, WMS allocation screens, and shipping validations completely flat, simple, and extremely fast, avoiding intermediate procurement-module joins.

### 2. Lineage Ancestry Tracking Field
To satisfy the auditing and trace requirements (e.g. *"Which PO or arrival shipment brought in the physical stock that fulfilled this sales order hold?"*) without cluttering primary operational references, we added a nullable, optional foreign key column `origin_arrival_item` to `StockReservation` pointing back to `procurement.ArrivalItem`:

```python
origin_arrival_item = models.ForeignKey(
    'procurement.ArrivalItem',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='physical_reservations',
    help_text="The incoming shipment line that fulfilled this physical reservation hold"
)
```

### 3. Automated Receipt Promotion Pipeline
The promotion execution is hooked directly into `ArrivalService.finalize_from_movement(movement, user)`, which runs inside the atomic transaction triggered when an inbound `STOCK_ARRIVAL` movement is completed:
- For each received `ArrivalItem`, the system queries all active `ArrivalReservation` records.
- It locates the corresponding physical `Stock` lot created/updated by the inbound receipt.
- Loop over active future reservations and promote them:
  1. Create a `StockReservation` holding physical stock lot with `origin_arrival_item = arrival_item` and direct links to the customer's Sales Order.
  2. Locate matching `SalesAllocation` records and transition them: swap `source_type` from `ARRIVAL` to `STOCK`, bind `physical_reservation = physical_lock`, and clear `arrival_reservation = None`.
  3. Support partial receiving: if received quantity is less than expected, promote received portions and gracefully reduce remaining `ArrivalReservation` quantities rather than deleting them.
  4. Delete fully promoted `ArrivalReservation` records.
  5. Synchronize the `Stock` lot's `reserved_qty`.

## Consequences

### Positive:
- **Operational Clarity & Speed**: Pickers, shipping operators, and WMS dashboards immediately see the Sales Order as the direct parent of the hold without traversing procurement arrival relationships.
- **Absolute Lineage Traceability**: Stock controllers and auditors can trace physical holds back to the exact incoming cargo lot and PO via `origin_arrival_item` for quality or supplier compliance checks.
- **Zero Manual Intervention**: Reconciling holds and allocations once arrivals land is completely automated, eliminating human errors and data inconsistencies.
- **Robust Partial Fulfillments**: Cleanly handles under-received shipments by converting only what arrived to physical locks and leaving remaining balances in future reservations.

### Negative:
- Adds a cross-module database reference (`origin_arrival_item`) between `inventory` and `procurement` models. This is safely mitigated by setting `on_delete=models.SET_NULL` to prevent cascading deletions.
