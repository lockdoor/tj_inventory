# Implementation Plan: Procurement & Split Allocation System

This plan outlines the technical implementation of the `procurement` app, focusing on the **Split Allocation** logic that allows a single demand (Reservation) to be satisfied by multiple sources: Physical Stock, Expected Arrivals, and Shortages.

## User Review Required

> [!IMPORTANT]
> **Allocation Priority**: The current plan assumes a "Physical Stock First" priority. If we need to reserve specific incoming lots for specific customers even if stock is on hand, we will need to add a "Priority" field to the Allocation Engine.

> [!NOTE]
> **Concurrency**: High-volume reservation requests will require database-level locking (`select_for_update`) to prevent over-allocating the same stock units.

## ERD Concept & Model Architecture

The core of this system is the separation between **Demand (Reservation)** and **Fulfillment (Allocation)**.

### 1. Arrival Management (The Supply)
- **`Arrival`**: Header for incoming shipments.
  - `document_no`, `expected_date`, `status` (SCHEDULED, IN_TRANSIT, RECEIVED, CANCELLED), `partner`, `warehouse`.
- **`ArrivalItem`**: Specific lines in the shipment.
  - `item`, `expected_qty`, `received_qty`, `unit_cost`.

### 2. Reservation & Allocation (The Demand)
- **`Reservation`**: Represents the total requirement from a source (e.g., Sales Order).
  - `document_no`, `item`, `total_qty`, `status` (PENDING, PARTIAL, ALLOCATED, COMPLETED).
- **`Allocation`**: The "Links" that satisfy the reservation.
  - `reservation` (FK)
  - `quantity` (The portion of the total qty)
  - `type` (PHYSICAL, ARRIVAL, SHORTAGE)
  - `warehouse` (Nullable, for PHYSICAL)
  - `arrival_item` (Nullable, for ARRIVAL)
  - `status` (ACTIVE, FULFILLED, CANCELLED)

## Business Logic: The Allocation Engine

The `AllocationService` will implement the following logic when a new `Reservation` is created:

### 1. The Allocation Algorithm
```python
def allocate_stock(reservation_request):
    remaining_qty = reservation_request.qty
    
    # Step A: Check Physical Stock
    physical_stock = Stock.get_available(item)
    if physical_stock > 0:
        take = min(remaining_qty, physical_stock)
        create_allocation(type='PHYSICAL', qty=take)
        remaining_qty -= take
        
    # Step B: Check Expected Arrivals (if remaining > 0)
    if remaining_qty > 0:
        upcoming_arrivals = ArrivalItem.get_available(item)
        for arrival in upcoming_arrivals:
            take = min(remaining_qty, arrival.available_qty)
            create_allocation(type='ARRIVAL', qty=take, arrival_item=arrival)
            remaining_qty -= take
            if remaining_qty == 0: break
            
    # Step C: Mark Shortage (if remaining > 0)
    if remaining_qty > 0:
        create_allocation(type='SHORTAGE', qty=remaining_qty)
```

### 2. Auto-Promotion Logic
When an `Arrival` status changes to `RECEIVED`:
1.  Identify all `Allocation` records linked to the `ArrivalItem`s of that document.
2.  Trigger a "Promotion" event that converts `ARRIVAL` type allocations into `PHYSICAL` type, linking them to the newly created `Stock` records.

## Proposed Changes

### [procurement]

#### [NEW] [models.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/models.py)
Define `Arrival`, `ArrivalItem`, `Reservation`, and `Allocation` models with appropriate `choices` and `related_names`.

#### [NEW] [services.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/services.py)
Implement `ProcurementService` with methods for:
- `create_arrival()`
- `process_reservation()` (The Allocation Engine)
- `promote_allocations()` (Handle arrival receipts)

#### [NEW] [views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/views.py)
- `ArrivalListView`, `ArrivalCreateView`
- `ShortageDashboardView`: A specialized view for Stock Controllers to see all `SHORTAGE` allocations.

## Verification Plan

### Automated Tests
- `test_allocation_split`: Verify 1000 units split into 500/300/200 correctly.
- `test_arrival_promotion`: Verify that receiving an arrival updates pending allocations.

### Manual Verification
- Create a Reservation for more stock than exists.
- Check the "Shortage Dashboard" to see if it appears correctly.
- Create an Arrival and see the shortage decrease.
