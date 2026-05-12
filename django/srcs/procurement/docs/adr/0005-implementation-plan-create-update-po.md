# Implementation Plan: Purchase Order Form with Inline Items

This plan describes how to implement a unified Create/Update form for Purchase Orders, allowing the Stock Controller to manage both the PO header and multiple line items on a single page, mirroring the experience of inventory movements.

## User Review Required

> [!NOTE]
> **Dynamic Rows**: The template will include JavaScript to allow users to add or remove item lines dynamically without page reloads, using the same pattern as `movement_create.html`.

## Proposed Changes

### 1. [procurement] (Forms)

#### [NEW] [forms.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/forms.py)
- `PurchaseOrderForm`: Header form for PO details (Document No, Partner, Expected Date, Note).
- `PurchaseOrderItemForm`: Individual line item form (Item, Order Qty, Unit Cost).
- `PurchaseOrderItemFormSet`: Inline formset created via `inlineformset_factory`.

### 2. [procurement] (Views)

#### [MODIFY] [views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/views.py)
- `PurchaseOrderCreateView`: 
    - Handles GET/POST for both `PurchaseOrderForm` and `PurchaseOrderItemFormSet`.
    - Saves both in an atomic transaction.
- `PurchaseOrderUpdateView`:
    - Handles updates for existing POs.
    - Restricts editing to POs in `DRAFT` status.

### 3. [procurement] (Templates)

#### [NEW] [purchase_order_form.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/templates/procurement/purchase_order_form.html)
- A high-fidelity template following the glassmorphism design.
- **Section 1: Header**: Grid layout for PO details.
- **Section 2: Line Items**: Dynamic table where rows can be added/removed.
- Includes total calculation logic (optional but helpful).

### 4. [procurement] (Routing)

#### [MODIFY] [urls.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/urls.py)
- Add paths for `purchase-order-create` and `purchase-order-update/<pk>/`.

### 5. [tests] (Business Logic)

#### [NEW] [test_po_logic.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/tests/procurement/services/test_po_logic.py)
- Test basic business rules:
    - Cannot update non-draft POs.
    - Document No must be unique.
    - Partner must be a supplier.

## Verification Plan

### Automated Tests
- Run `pytest django/srcs/tests/procurement/` to verify logic.

### Manual Verification
1. Navigate to "New Purchase Order".
2. Fill in header details.
3. Add multiple item rows with quantities and costs.
4. Save and verify the PO and its items are correctly recorded in the database.
5. Try to edit the PO and verify changes are saved.
