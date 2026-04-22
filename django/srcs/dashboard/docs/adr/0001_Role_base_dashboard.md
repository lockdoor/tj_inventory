# Implementation Plan - Role-Based Dashboards

The goal is to transition from a single generic dashboard to a role-based system. Users will be automatically directed to the dashboard that best suits their responsibilities (Executive vs. Warehouse Admin).

## User Review Required

> [!IMPORTANT]
> - **Role Priority**: If a user is in multiple groups, the "Executive" role will take precedence for dashboard display.
> - **New Dashboards**: We will introduce a specialized `Warehouse Dashboard` that highlights operational metrics (e.g., Stock Summary).

## Proposed Changes

### Dashboard Module

#### [MODIFY] [dashboard_views.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/dashboard/views/dashboard_views.py)
- Refactor `DashboardView` to detect user roles.
- Overwrite `get_template_names()` to return the specific template based on role.
- Define `get_executive_context` and `get_warehouse_context`.
- Add metrics for the warehouse dashboard (using `StockCard` and `InventoryMovement` models).

#### [NEW] [executive_dashboard.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/dashboard/templates/dashboard/executive_dashboard.html)
- Specialized template for Executives (Launcher style).

#### [NEW] [warehouse_dashboard.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/dashboard/templates/dashboard/warehouse_dashboard.html)
- Specialized template for Warehouse Admins (Operational Metrics style).

#### [DELETE] [overview.html](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/dashboard/templates/dashboard/overview.html)
- Remove the old generic dashboard template once new ones are verified.

### Inventory Module (Support)

#### [NEW] [stock_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/inventory/services/stock_service.py)
- Add a `get_warehouse_summary` method to calculate metrics needed for the dashboard (total items, total stock, recent movements).

## Verification Plan

### Automated Tests
- No new automated tests, but I will verify by manually assigning different groups to a test user.

### Manual Verification
1. Login as a user in the `executive` group -> Verify all 3 modules are visible and title is "Executive Dashboard".
2. Login as a user in the `warehouse_admin` group -> Verify only "Catalog" and "Inventory" are visible, and the "Warehouse Control Center" title appears with stock metrics.
