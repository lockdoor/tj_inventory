# ADR 0001: Sales Reservation Strategy (Triple-Ledger Architecture)

## Status
Accepted (Revised 2024-05-14)

## Context
Standard inventory systems often struggle with "Pre-orders" and "Stock Gaps". We need a way to promise stock to customers across three different scenarios:
1. We have it on the shelf (**Actual Stock**).
2. It's on a truck coming to us (**Arrival Stock**).
3. We don't have it at all (**Shortage/Gap**).

## Decision
We implement a **Triple-Ledger Architecture** that decouples the "Fulfillment Plan" from the "Physical Lock".

### 1. The Strategy Map (`SalesAllocation`)
The Sales module maintains the master map of how a `SalesOrderItem` will be fulfilled. It splits the requested quantity into one or more allocations:
- **STOCK**: Linked to a physical `StockReservation` in the Inventory app.
- **ARRIVAL**: Linked to an `ArrivalReservation` in the Procurement app.
- **SHORTAGE**: Linked to a `Shortage` record to signal procurement needs.

### 2. Sourcing & Allocation Logic
When an order is processed, the `SalesService` follows a strict waterfall priority:
1. **Physical Lock**: Attempt to reserve physical lots via `inventory.ReservationService`. This creates a hard hold on specific lots.
2. **Future Lock**: If physical stock is exhausted, attempt to reserve against incoming shipments via `procurement.ArrivalReservationService`.
3. **Gap Logging**: Any remaining quantity is recorded as a `Shortage`.

### 3. Explicit Synchronization
Instead of signals, we use explicit Service-to-Service calls:
- `SalesService` calls `ReservationService.reserve()` -> Inventory module updates `Stock.reserved_qty`.
- `SalesService` calls `ArrivalReservationService.reserve_future()` -> Procurement module updates `ArrivalItem.reserved_qty`.

### 4. Promotion Workflow (Arrival to Stock)
When an `Arrival` is received in the warehouse:
1. The future `ArrivalReservation` is deleted.
2. A new physical `StockReservation` is created.
3. The `SalesAllocation` is updated from `ARRIVAL` to `STOCK`.

## Consequences
- **Positive**: High accuracy in "Available-to-Promise" (ATP).
- **Positive**: Clean domain separation; the Warehouse Admin only sees physical holds, while the Stock Controller only sees shipment holds.
- **Positive**: Precise visibility for Sales on *exactly* why an order is delayed.
- **Negative**: Requires careful coordination during the "Arrival -> Stock" conversion phase.
