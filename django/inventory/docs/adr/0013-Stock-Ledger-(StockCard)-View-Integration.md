# Plan: Stock Ledger (StockCard) View Integration

Implementing a comprehensive audit trail interface for the `StockCard` model, providing users with a chronological ledger of all inventory transactions.

## Proposed Changes

### [Component] Inventory Views
#### [NEW] [stockcard_views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/views/stockcard_views.py)
- Create `StockCardListView`: Paginated list of all ledger entries, sorted newest first.
- Create `StockCardDetailView`: Deep-dive view of a specific audit entry, including source movement references.

#### [MODIFY] [__init__.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/views/__init__.py)
- Export the new views.

### [Component] Inventory URLs
#### [MODIFY] [urls.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/urls.py)
- Register endpoints:
    - `/inventory/ledger/` -> `stockcard-list`
    - `/inventory/ledger/<int:pk>/` -> `stockcard-detail`

### [Component] UI / Templates
#### [NEW] [stockcard_list.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/templates/inventory/stockcard_list.html)
- High-fidelity glassmorphism table.
- Reuses pagination logic from the Movements list.
- Columns: Date, Item, Warehouse, Lot, Type, Quantity.

#### [NEW] [stockcard_detail.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/templates/inventory/stockcard_detail.html)
- Detailed card layout showing snapshot data.
- Direct links to parent movement documents where applicable.

## Verification Plan

### Automated Tests
- `test_stockcard_list_pagination`: Verify that pagination works and shows 15 items per page.
- `test_stockcard_detail_view`: Verify all snapshot fields (item, lot, quantities) are displayed correctly.

### Manual Verification
- Navigate to the Stock Ledger.
- Click a row to view deep details.
- Verify "Source Movement" link correctly redirects to the movement document.
