# ADR 0019: Inventory Stock Reservation System

## Status
Accepted

## Context
As the system scales to handle pre-orders and sales orders, we need a mechanism to ensure that stock promised to a customer is not accidentally shipped to another. We need a clear distinction between "Physical Reality" and "Sales Strategy."

## Decision
We will implement a **Hard Physical Reservation** system within the `inventory` module.

### 1. Physical-Only Scope
The `StockReservation` model in the inventory module will exclusively track reservations against **Actual Stock** (items physically present in the warehouse). It will not track future arrivals or shortages; those are handled by the `sales` and `procurement` modules respectively.

### 2. Atomic Reservations
Reservations must be created against a specific **Stock** record (Item + Warehouse + Lot). This ensures that we know exactly which physical units are "locked."

### 3. Service-Layer Orchestration
To maintain domain integrity, all reservation operations (reserve, release, update) must be performed through the `ReservationService`. This service will handle validation (e.g., checking available balance) and ensuring atomic updates.

### 4. Cross-Module Traceability
Each reservation must store a `reference_no` and `reference_type` (e.g., "SO-101", "sales_order"). This allows the Warehouse Admin to see *who* is holding the stock without needing access to the Sales module's internal tables.

## Consequences
- **Positive**: Prevents over-shipping and "stock theft" between orders.
- **Positive**: Provides the Warehouse Admin with a clear "Hold" report.
- **Positive**: Decouples Inventory from Sales; Sales simply "calls" the Inventory service to lock stock.
- **Negative**: Adds overhead to every stock-related transaction to check for active reservations.
