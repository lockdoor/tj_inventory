# Inventory Movement Detail View Implementation Plan

This plan covers the implementation of the detailed view for specific inventory documents (Inbound/Outbound). It focuses on high-precision data display, including itemized lists and audit trail integration.

## User Review Required

> [!IMPORTANT]
> **Audit Visibility**: If a movement is `completed`, I will display the corresponding `StockCard` entries directly in a side-pane or below the items to provide a clear audit trail of the balance impact.
> **Permissions**: Access will require `inventory.view_inventorymovement`.

## Proposed Changes

### 1. View & URL Routing
#### [MODIFY] [movement_views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/views/movement_views.py)
- Implement `MovementDetailView` inheriting from `LoginRequiredMixin`, `PermissionRequiredMixin`, and `DetailView`.
- Context Data:
  - `items`: Fetch `MovementItem.objects.filter(movement=self.object).select_related('item')`.
  - `audit_trail`: If completed, fetch `StockCard.objects.filter(movement=self.object)`.

#### [MODIFY] [urls.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/urls.py)
- Add `path('movements/<str:document_no>/', views.MovementDetailView.as_view(), name='movement-detail')`.

### 2. User Interface
#### [NEW] [movement_detail.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/templates/inventory/movement_detail.html)
- **Aesthetic**: Premium "Emerald Green" glassmorphism with a two-pane layout:
  - **Left/Top**: Document Header (Doc No, Date, Type, Partner, Warehouse).
  - **Main**: Itemized Table (SKU, Name, Quantity, Lot, Remark).
  - **Right/Bottom**: Audit Ledger (Stock Card impacts).
- **Navigation**: Integrated breadcrumbs (`Inventory / Movements / [Doc No]`).

### 3. Verification & Testing
#### [MODIFY] [test_movement_views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/tests/inventory/views/test_movement_views.py)
- Add tests for `MovementDetailView` permission gating.
- Verify 404 behavior for invalid document numbers.

## Verification Plan

### Automated Tests
- Run `pytest tests/inventory/views/test_movement_views.py`.

### Manual Verification
- Navigate from the Movement List to a specific Transaction Detail.
- Verify status-based UI changes (Draft vs Completed).
