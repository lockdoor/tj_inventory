This plan focuses on refactoring the `procurement` app to its smallest viable form, focusing exclusively on **Supply Tracking (Purchase Orders & Arrivals)**. Use this plan instead plan 0001.

## User Review Required

> [!IMPORTANT]
> **Minimalist Scope**: All reservation, allocation, and shortage logic is removed from this phase. The app will focus purely on tracking what is ordered and what arrives.

> [!NOTE]
> **Fulfillment Tracking**: The `ArrivalItem` will include an optional link to `PurchaseOrderItem` to allow tracking of partial deliveries.

## Proposed Changes

### 1. [procurement] (Supply Focus)

#### [NEW] [models.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/models.py)
- `PurchaseOrder` & `PurchaseOrderItem`: The formal order to a supplier.
- `Arrival` & `ArrivalItem`: The receipt of goods.
    - `ArrivalItem` has an optional `po_item_id` to link back to the source order.

#### [NEW] [services.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/services.py)
- `ProcurementService`: Basic CRUD for POs and Arrivals.
- `ReceiptService`: Handles the logic of converting an `Arrival` into `inventory.Stock` movements (Integration).

### 2. External Dependencies
- `catalog.Item`
- `partners.Partner`
- `inventory.Warehouse` & `inventory.Stock`

## Verification Plan

### Automated Tests
- `test_split_allocation`: Reserve 100 units where 40 are physical and 60 are incoming.
- `test_shortage_tracking`: Ensure 0 stock results in a `SHORTAGE` allocation.
- `test_arrival_to_physical_promotion`: Verify that receiving an Arrival updates the linked Allocations.

### Manual Verification
1. Create an Arrival for Item A (100 units).
2. Create a Reservation for Item A (150 units).
3. Verify: 100 units allocated to Arrival, 50 units allocated to Shortage.
4. Receive the Arrival and verify the 100 units move to Physical Allocation.
