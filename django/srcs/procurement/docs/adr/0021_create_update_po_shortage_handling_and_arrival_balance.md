# ADR 0021: Purchase Order Shortage Integration and Reusable Arrival Fulfillment Balance Layout

## Status
Accepted (2026-06-17)

## Context
In the procurement workflow:
1. **Shortages** represent immediate inventory demands from Sales or Production. Procurement agents need to quickly draft or update Purchase Orders (POs) to fulfill these shortages, keeping a clear lineage link from shortage requests to specific PO items.
2. **Arrival Fulfillment Balance** is a critical visualization showing how incoming shipments satisfy pre-sold commitments. To prevent duplicate template logic and maintain visual consistency, this layout needs to show up in both Purchase Order Details (which lists multiple related arrivals) and Arrival Details (which shows a single shipment's balance). The math must clearly distinguish between pre-sold reservations (`Reserved`), received/finalized reservations (`Promoted`), and uncommitted capacity (`Available`).

## Decision
We implemented comprehensive shortage-handling logic during PO creation/updating, and structured the arrival balance visualization using reusable Django template partials:

### 1. Purchase Order & Shortage Integration
* **Creation and Update Forms**:
  - The [purchase_order_form.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/templates/procurement/purchase_order_form.html) dynamically pulls active pending shortages for selected items, showing detailed shortage quantities and reference tags to the agent.
  - Linking shortages dynamically populates the PO line items list and updates relevant quantities automatically.
* **Fulfillment Traceability**:
  - Under the "Order Items" card in [purchase_order_detail.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/templates/procurement/purchase_order_detail.html), linked shortages are explicitly rendered, showing their reference codes and requested quantities.
* **Automatic Lifecycle Reversals**:
  - Shortages are reverted to `pending` status if the corresponding PO item line is deleted during a PO update, or if the parent PO is deleted or cancelled.

### 2. Reusable Arrival Fulfillment Balance Layout
To avoid duplicating complex layout code, we extracted the arrival balance presentation into two template partials:
* **`arrival_fulfillment_balance.html`**:
  - Wraps the glass-card structure, title, and headers.
  - Dynamically supports both a list of shipments (`arrivals_list`) and a single shipment (`arrival`), looping over them accordingly.
* **`arrival_fulfillment_balance_item.html`**:
  - Renders a clean tabular layout for a single shipment line showing the columns:
    - **Expected**: Total expected units in base pieces (`expected_pieces`).
    - **Reserved**: Active pre-sold commitments (`reserved_qty`).
    - **Promoted**: Commitments that have transitioned to physical stock reservations after landing (`promoted_qty`).
    - **Available**: Remaining expected units after deducting active and promoted reservations (`expected_pieces - reserved_qty - promoted_qty`).

### 3. Page Integrations
* **Purchase Order Detail Page**:
  - Replaced the hardcoded layout with a simple include pointing to the new partial, passing the sorted list of all related non-cancelled arrivals:
    ```html
    {% if arrivals %}
        {% include "procurement/partials/arrival_fulfillment_balance.html" with arrivals_list=arrivals %}
    {% endif %}
    ```
* **Arrival Detail Page**:
  - Embedded the same card in the left column below items and movements:
    ```html
    {% if arrival.status != 'cancelled' %}
        {% include "procurement/partials/arrival_fulfillment_balance.html" with arrival=arrival %}
    {% endif %}
    ```

## Consequences
* **Positive**: Visual consistency across both PO detail and Arrival detail pages.
* **Positive**: Clear division of incoming balance states (Expected, Reserved, Promoted, Available) ensures procurement officers can trace pre-sold versus stock-bound inventory.
* **Positive**: Decoupled, DRY layout architecture simplifies template maintenance and reduces visual bugs.
