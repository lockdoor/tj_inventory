# ADR 0006: Inventory Representation Layer

## Status
Completed

## Context
The inventory engine's core logic is complete. To make it accessible to users, we need a high-fidelity diagnostic and operational overview that fits the "Executive Dashboard" paradigm.

## Decisions
1.  **Dashboard Module**: Added a dedicated "Inventory Engine" entry point on the main executive dashboard under the "Core Engine" badge.
2.  **Modular Hub**: Created a central Inventory Overview page with four primary management cards:
    -   **Warehouses**: For physical locations.
    -   **Movements**: For document-driven inventory changes.
    -   **Stock Balances**: For real-time lot visibility.
    -   **Stock Cards**: For transactional audit history.
3.  **Security Integration**: 
    -   `LoginRequiredMixin`: Access is restricted to authenticated users.
    -   `PermissionRequiredMixin`: Access is restricted to users with `inventory.view_warehouse`.
4.  **Visual Language**: Consistent use of the Emerald Green glassmorphism theme, with Lucid-style SVG icons for intuitive navigation.

## Verification
-   Verified `DashboardView` module registration.
-   Verified `InventoryOverviewView` routing and permission checks.
-   Verified `inventory/overview.html` visual fidelity.
