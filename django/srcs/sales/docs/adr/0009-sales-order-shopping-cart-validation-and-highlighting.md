# ADR 0009: Interactive Sales Order Shopping Cart Validation, Highlighting, and Safe Deletion

## Status
Accepted (2026-06-12)

## Context
Our Sales Order creation and modification interface (`sales_order_create.html`) leverages an interactive client-side shopping cart. This cart serializes items to a hidden JSON input (`items_json`) before submission to the Django backend.
* **Conflicting Input Edits**: Previously, users could modify the Price, Qty, and Packaging values of a product in the catalog grid *after* that item had already been added to the shopping cart. This led to discrepancies between what the catalog UI showed and what was stored in the cart state.
* **Accidental Deletions**: Removing items from the shopping cart was immediate and had no confirmation, leading to accidental deletions.
* **Stale Backend Reservations**: In Update/Edit mode for draft orders, removing a line item in the frontend did not release backend database reservations (such as `StockReservation`, `ArrivalReservation`, and `Shortage`) until the entire form was re-submitted. This caused inventory locks to remain active unnecessarily, preventing other orders from utilizing the allocated stock.

## Decision
We implemented a set of frontend constraints, a confirmation dialog, and a synchronized backend deletion endpoint to protect cart items and release reserved inventory resources immediately.

### 1. Catalog Selection Locking and Highlighting
* **Visual Highlights**: Added an `.in-cart-highlight` style state. When a catalog item is in the cart, its card is highlighted with an emerald border and a subtle background tint.
* **Input Protection**: All editing controls on the catalog card (Price, Qty, and Packaging Select) and the "Add" button are disabled when the item is detected in the cart:
  ```javascript
  const isInCart = cart.some(c => c.item_id === item.id);
  const disabledAttr = isInCart ? 'disabled' : '';
  ```
* **User Guide Notice**: A helper label is displayed instructing the user: *"Remove from cart to edit details"*, preventing confusing parallel updates.
* **Initial Render Fix**: The `renderCatalog()` routine is executed at the very beginning of `updateCart()`, before checking if `cart.length === 0`. This ensures that even when the cart starts empty (e.g. creating a new order), the catalog items are still fully loaded and displayed.

### 2. Custom Delete Confirmation Modal
* **Modal Gating**: Removed direct/immediate cart removals. Clicking the trash icon opens a custom glassmorphic modal (`#delete-cart-item-modal`).
* **Dynamic Warning Messages**: The modal content adapts dynamically:
  - In creation mode: warns the user about removing the item from their local shopping cart.
  - In edit/update mode: explicitly warns the user that deleting the item will immediately erase the line on the backend and release all reservations.

### 3. Immediate Backend Deletion Endpoint (Edit Mode)
* **SalesOrderItemDeleteView**: Registered `/sales/orders/<order_id>/items/<item_id>/delete/` as an AJAX POST endpoint.
* **Atomic Deletion & Signal Cascades**:
  - The backend view performs a database deletion on `SalesOrderItem` inside a database transaction.
  - Deleting the `SalesOrderItem` automatically triggers the pre-delete signal receiver (`cleanup_sales_order_item_allocations_and_reservations`), which clean-releases associated reservations and shortages.
* **Frontend Sync**: The client performs a `fetch()` request to this endpoint. On success, the item is removed from the local JavaScript array (`cart.splice(idx, 1)`) and the UI is re-rendered.

## Consequences
* **Positive**: Enforces consistency between the catalog inputs and the cart array, preventing conflicting edits.
* **Positive**: Mitigates the risk of accidental item deletion through a confirmation modal.
* **Positive**: Free up locked inventory allocations (physical stock reservations, arrival reservations, shortages) immediately when items are removed from a draft sales order, rather than waiting for form submission.
* **Positive**: Ensures clean page loading for new orders by guaranteeing `renderCatalog` runs even with an empty cart.
