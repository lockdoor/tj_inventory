# ADR 0006: Sales Order Status Transitions, Auto-Confirmation, and WMS Release Workflow

## Status
Accepted (2026-05-27)

## Context
A Sales Order is a commercial document that tracks customer commitments, whereas an Inventory Movement is a physical warehouse execution document (picking list / delivery order). 
* **The Sourcing-Fulfillment Gap**: Previously, there was no connection between office sales commitments and physical warehouse shipments. Planners could allocate stock, but WMS staff had to manually record shipments without link-tracking, raising data integrity and double-picking risks.
* **Status Lifecycles**: The business model defines a clear status transition path:
  1. `DRAFT`: Order creation and allocation planning.
  2. `CONFIRMED`: Sourcing is 100% complete with physical stock lot holds.
  3. `PREORDER`: Sourcing relies on scheduled procurement arrivals or dynamic shortages.
  4. `PROCESSING`: Order released to the warehouse floor for physical picking and packing.
  5. `SHIPPED`: Goods depart the warehouse, deducting actual stock balances.
* **Integrity During Picking**: While goods are in `PROCESSING` status, the physical stock is active on the floor. The associated `StockReservation` holds must remain locked during this picking phase to prevent other orders from stealing the stock.
* **Status Blocking**: Users were getting stuck in `DRAFT` because there was no action handler or button to confirm the order and transition it to `CONFIRMED` or `PREORDER`, locking them out of WMS releases.

## Decision
We implement a robust, bidirectional sync connecting Sales Order planning directly to physical WMS execution.

### 1. Sourcing Lock & Auto-Promotion (`check_and_promote_order_status`)
We introduced an automated status promotion helper:
* If all lines in an order are 100% allocated via physical stock lot reservations (shortages are zero and arrivals are zero), the order status is promoted to `CONFIRMED`.
* Wired this check to execute automatically inside both `SalesOrderRefreshAllocationView` and `SalesOrderConfirmView` POST actions. This automatically promotes `PREORDER` orders to `CONFIRMED` as soon as inbound shipments arrive and allocations are refreshed.
* Created `SalesOrderConfirmView` (POST endpoint `/orders/<int:pk>/confirm/`) to allow planners to explicitly confirm `DRAFT` orders. If outstanding shortages exist, it transitions the order to `PREORDER`.

### 2. Secure Warehouse Release View (`SalesOrderReleaseToWarehouseView`)
* Created a POST-only action handler gated securely under the `'sales.change_salesorder'` permission.
* Validates that the order is `CONFIRMED`. 
* Transitions the status to `PROCESSING` and calls `MovementService.create_outbound_from_reservations` atomically.

### 3. WMS Picking Generation & Grouping (`movement_service.py`)
* Implemented `MovementService.create_outbound_from_reservations(sales_order, user)`:
  * Groups active reservations by warehouse to support multi-warehouse fulfillment.
  * Generates one Draft Outbound `InventoryMovement` per warehouse involved (document number: `OUT-{SO_DOC}-{WH_CODE}`).
  * Populates `InventoryMovementItem` lines with the exact items, quantities, and lot numbers held by the reservations.

### 4. Bidirectional Sync on Completion and Reversion
* ** Fulfill & shipped (`complete_movement`)**:
  * Upon marking the Outbound Movement as `COMPLETED`, the transaction deducts physical stock balances, creates `StockCard` audit ledgers (type: `OUT`), increments `fulfilled_qty` on sales items, releases/deletes `StockReservation` holds, and transitions the parent `SalesOrder` status to `SHIPPED`.
* ** Restore & Revert (`revert_to_draft`)**:
  * If a completed Outbound Movement is reverted to `DRAFT`, the transaction decrements `fulfilled_qty`, restores the physical `StockReservation` holds, and demotes the Sales Order status back to `PROCESSING`.

### 5. UI Upgrades & Linked WMS Documents (`sales_order_detail.html`)
* **Confirm Order Button**: A bright emerald-styled POST button visible next to "Edit Order" when in `DRAFT` status.
* **Release to Warehouse Button**: A bold blue-styled button visible on the header when in `CONFIRMED` status.
* **WMS Outbound Documents Card**: A dedicated glassmorphic card placed in the left sidebar showing active/completed outbound pick slip lists with real-time status badges and active deep-links to details.

### 6. Verification Suite (`tests/sales/test_sales_transitions.py`)
Developed comprehensive integration tests verifying:
* Confirming orders transitions status correctly.
* Refreshing allocations promotes `PREORDER` to `CONFIRMED` upon stock replenishment.
* WMS completion deducts stock, releases locks, and transitions Sales Order to `SHIPPED`.
* WMS reversion back to draft safely re-locks stock and demotes order status to `PROCESSING`.

## Consequences
* **Positive**: Absolute alignment with enterprise ERP/WMS best practices.
* **Positive**: Zero risk of stockout or double-picking during physical operations because reservations remain locked until the movement is completed.
* **Positive**: Bidirectional database transactions prevent database state corruption during reversals.
* **Positive**: High-fidelity dashboard visibility gives office staff instant tracking of pick slip completion states.
