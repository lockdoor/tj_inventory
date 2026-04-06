# ADR 0007: Inventory Movement List View

## Status
**Completed** (2026-04-06)

## Context
The Inventory module requires a centralized, secure, and performant ledger to track all stock documents (Inbound and Outbound). This dashboard serves as the operational hub for Warehouse Admins and Executives to monitor the flow of goods across the system.

## Decision
We implemented a dedicated list view for inventory movements with the following architectural and design constraints:

1.  **View Logic**: Used Django's `ListView` with `select_related('warehouse', 'partner')` to optimize performance and prevent N+1 query issues.
2.  **Pagination**: Enforced a strict pagination limit of **10 items per page** to maintain UI clarity and performance.
3.  **Security (RBAC)**: Gated the view behind the `inventory.view_inventorymovement` permission using `PermissionRequiredMixin` with `raise_exception=True`.
4.  **UI/UX**: Adopted a premium "Emerald Green" glassmorphism theme:
    -   Integrated breadcrumbs (`Inventory / Movements`) for consistent navigation.
    -   Custom-styled centered pagination menu with a result summary.
    -   Status-aware badges and direction-specific icons for transactions.

## Implementation Details

### Permissions
Updated the `seed_groups` management command to provision the following for Executive and Warehouse Admin roles:
- `inventory.view_inventorymovement`
- `inventory.add_inventorymovement`
- `inventory.change_inventorymovement`
- `inventory.delete_inventorymovement`

### Components
- **View**: `MovementListView` in `inventory/views/movement_views.py`
- **URL**: `path('movements/', views.MovementListView.as_view(), name='movement-list')`
- **Template**: `inventory/templates/inventory/movement_list.html`

## Consequences
- **Positive**: Provides a unified, secure entry point for auditing all stock flow.
- **Positive**: Standardizes the "Emerald Green" design language for list views across the inventory module.
- **Neutral**: Requires `seed_groups` to be run to provision access for existing users.
