# ADR 0004: Sales Order Detail, Manual Sourcing Workspace, and State Protection

## Status
Accepted (2026-05-26)

## Context
Sales orders must be allocated dynamically using physical warehouse stock lots and scheduled procurement arrivals. Planners and stock controllers need a premium interface to monitor sourcing allocations, review timelines, and manually override automatic reservations.
* **Expected Fulfillment Date Clarification**: Planners require clarity that the sales order's date field represents the *Expected Fulfillment Date* (when items are shipped to customers), and that scheduled supplier arrivals must land on or before this date to be eligible for sourcing.
* **Sourcing Diagnostics visibility**: Planners need a detailed, transparent breakdown of each line item's active allocations (Warehouse Lots, Procurement Inbound deep-links, and Dynamic Material Shortage ledger entries).
* **Manual Override Ownership**: If a planner manually customizes allocations for a line item (even if they allocate nothing, leaving the fields empty), the system must respect this intent and bypass the automatic FEFO and arrivals engines, keeping the remaining gap as a dynamic procurement shortage.
* **Soft-Deleted Inbound Protection**: The system must actively prevent manual or automatic reservations from binding to supplier arrivals that have been soft-deleted.
* **Timeline Integration**: Dynamic material shortages logged in the sell order context should carry over the sales order's expected fulfillment date as their expected timeline target for procurement.

## Decision
We implement a high-fidelity **Sales Order Sourcing Diagnostics Page** and a dedicated **Manual Allocation Workspace**, protected by strict transaction boundaries, date-range checks, soft-delete filters, and manual state bypass guards.

### 1. Sales Order Detail & Diagnostics UI (`sales_order_detail.html`)
* **Header Actions & Stats KPI Row**: Renders the overall order value (e.g. `฿1,200.00`), proportion of fully allocated lines, and expected fulfillment timeline. Gated actions like **"Refresh Allocations"** run the dynamic gap-filler engine with a single click.
* **Inline "Edit Order"**: Visible only when the order status is `DRAFT`, opening a premium, cart-rehydrated editing view.
* **Sourcing Diagnostics Drawer**: Under each ordered line item, a diagnostics grid displays active reservations:
  - **Stock Reservations**: Lists physical stock holds, warehouse codes, and lot numbers.
  - **Arrival Reservations**: Lists future procurement holds with direct deep-links to supplier arrival detail pages.
  - **Dynamic Shortages**: Displays gaps recorded in the material shortages ledger with direct links to PO status indicators (Pending, PO Created, Cancelled).
  - **Manual Sourcing Action Triggers**: Shows a **"Manual Allocate"** button if auto-allocated, or a **"Manually Locked"** padlock icon, **"Edit Sourcing"**, and **"Reset to Auto"** actions if overridden.

### 2. Manual Allocation Workspace (`sales_order_allocate.html`)
Provides a glassmorphic 2-column workspace for hand-picking inventory sourcing:
* **Context Sidebar**: Summarizes the line item details (requested qty, SKU, unit price).
* **Stock Lots & Arrivals Tables**: Lists available warehouse locations and scheduled supplier deliveries. Includes a **"Max"** button to automatically fill the maximum possible quantity.
* **Late Inbounds Filtering**: The GET view strictly filters out arrivals expected after the sales order fulfillment date (`arrival__expected_date__lte=order.order_date`), preventing planners from manual late-reserving.
* **Soft-Deleted Inbounds Protection**: Actively excludes soft-deleted arrivals (`arrival__is_deleted=False`) on both GET and POST requests, raising a validation error and redirecting if a deleted arrival is targeted.
* **Real-Time Interactive Summation Bar**: A floating sticky footer aggregates inputs and presents status states:
  - **Perfect Match (Green)**: Fulfill target matched.
  - **Sourcing Gap (Yellow)**: Under-allocated gap will convert to a supplier purchase requisition.
  - **Over-Allocated Error (Red)**: Sum exceeds request, automatically **disabling** the save button to maintain stock consistency.

### 3. Transactional Allocation Lifecycle & State Guards (`sales_order_views.py`)
To prevent race conditions, dirty reads, and user confusion over stock availability:
* **GET Workspace Release**: Loading the manual sourcing page immediately releases all current (manual and automatic) allocations for the line item inside an atomic transaction. This physically restores the stock lot available balances so the tables reflect correct true balances.
* **Cancel Rebuilds**: Clicking "Cancel" or "Reset to Auto" calls `refresh_allocation` on the line item with `is_manual_allocate = False`, immediately re-running automatic waterfall matching to restore dynamic reservations.
* **`is_manual_allocate` Model Flag**: We introduced a concrete database boolean field `is_manual_allocate` on `SalesOrderItem` to persist manual status.
* **FEFO & Arrivals Sourcing Bypass**: When `order_item.is_manual_allocate` is `True`, the smart allocator completely bypasses:
  1. `AUTO-SOURCING: ACTUAL STOCK (FEFO)`
  2. `AUTO-SOURCING: ARRIVALS`
  This respects the planner's explicit intent. Any remaining gap goes straight to shortage.
* **Empty Workspace Protection**: Posting the manual form with **neither** physical stock **nor** arrival selected sets `is_manual_allocate = True`. The engine bypasses stock/arrival auto-filling, converting the **entire requested quantity** into a dynamic shortage (supplier PO request).

### 4. Dynamic Shortage Expected Date Integration (`sales_service.py`)
To ensure supply chain timeline consistency, all automatic or manual shortages created within the sales order context carry over the expected fulfillment date:
```python
gap_record = ShortageService.create(
    item=order_item.item,
    request_qty=remaining_qty,
    user=order_item.order.created_by,
    reference_type=Shortage.ReferenceType.SELL_ORDER,
    reference_id=order_item.order.document_no,
    expected_date=order_item.order.order_date,  # Link shortage timeline to the SO fulfillment date
    note=f"Automatic shortage for {order_item.order.document_no}"
)
```

## Consequences
* **Positive**: Full control for planners to custom-source orders, backed by a visually premium UI.
* **Positive**: Strict timeline safety (late and deleted arrivals are securely filtered and blocked).
* **Positive**: Optimized database query performance by using the direct `is_manual_allocate` flag instead of repetitive subqueries.
* **Negative**: The temporary GET release briefly increases available warehouse levels for other sessions while editing, but is resolved atomically upon POST saving or GET cancellation.
