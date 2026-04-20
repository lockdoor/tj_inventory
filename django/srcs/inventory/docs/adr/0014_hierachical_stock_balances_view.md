# Plan: Hierarchical Stock Balances View

Implementing a multi-level inventory balance report that allows users to drill down from Warehouse locations to individual Item batches (Lots).

## User Review Required

> [!IMPORTANT]
> **Data Grouping**: We will implement the grouping logic in the view layer to ensure the template remains clean and efficient. 
> **Interactive Hierarchy**: The "Expand/Collapse" functionality will be implemented using vanilla JavaScript to provide a responsive, "app-like" experience without page reloads.

## Proposed Changes

### [Component] Inventory Views
#### [MODIFY] [stock_views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/views/stock_views.py)
- Create `StockBalanceListView`: 
    - Fetches all `Stock` records with `select_related('warehouse', 'item')`.
    - Groups data into a hierarchical dictionary: `Warehouse` -> `Item` -> `Lots`.
    - Calculates sub-totals for each Item and Warehouse.

#### [MODIFY] [__init__.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/views/__init__.py)
- Export `StockBalanceListView`.

### [Component] Inventory URLs
#### [MODIFY] [urls.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/urls.py)
- Register `/inventory/stock-balances/` -> `stock-balance-list`.

### [Component] UI / Templates
#### [NEW] [stock_list.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/templates/inventory/stock_list.html)
- **Hierarchical Layout**:
    - **Warehouse Level**: Top-level rows with location details and grand totals.
    - **Item Level**: Nested rows (collapsible) showing SKU-level balances.
    - **Lot Level**: Deepest level showing specific batch details.
- **Interactivity**:
    - Positive (`+`) / Negative (`-`) icons for toggling visibility.
    - Smooth glassmorphism transitions.
- **Visuals**:
    - Sticky headers for large lists.
    - Status indicators for low stock (optional but helpful).

## Verification Plan

### Automated Tests
- `test_stock_balance_grouping`: Verify the view correctly nests lots under items and warehouses.
- `test_stock_balance_totals`: Verify that item and warehouse totals match the sum of child lots.

### Manual Verification
- Verify that clicking `+`/`-` icons correctly reveals/hides child rows.
- Verify that footer totals are accurate for each group.
