# ADR 0002: Sales Dashboard and Sales Overview Design

## Status
Accepted (2026-05-22)

## Context
The inventory system serves multiple operational user profiles, each requiring tailored layouts, metrics, and workflows. 
* **Sales Representatives (`sales_rep` group)** need a focused command center to assess overall revenue performance, monitor order status counts, and reference product masters or customer databases.
* **Other Roles (Executives, Stock Controllers, Warehouse Admins)** need unified high-level access to the sales domain without cluttering their core interfaces.
* **Design Standards**: The system enforces a premium, modern design system based on glassmorphic styling, HSL tailwinds, responsive metrics grids, and micro-animations.
* **Performance**: Real-time sales stats and total revenue must be calculated efficiently without degrading page load speeds.

## Decision
We implement a dual-layer landing design consisting of a **Dynamic Role-Based Dashboard** and a **Dedicated Sales Domain Overview**, unified by optimized database aggregation and glassmorphic UI layout standards.

### 1. Dynamic Role-Based Dashboard Gating (`DashboardView`)
The main root landing view (`/`) dynamically resolves templates and contexts based on the user's prioritized group membership:
* **Role Priority**: Executive > Stock Controller > Warehouse Admin > Sales Rep > Default (Executive).
* **Sales Rep Dashboard (`dashboard/sales_dashboard.html`)**:
  - Serves as the high-level Sales home screen.
  - Dynamically builds a contextual dictionary `get_sales_context()` featuring a general stats panel and access to core modules (Sales Orders, Product Catalog, and Partner Network).
* **Optimized Local Imports**:
  - Models like `SalesOrder` and `SalesOrderItem` are imported dynamically inside context builder scopes to prevent cyclic import problems during application startup.

### 2. Dedicated Sales Domain Overview (`SalesOverviewView`)
To prevent cluttering the main dashboard and to provide a natural workflow step, we introduce a dedicated landing page for the Sales application (`sales:overview` pointing to `sales/overview.html`):
* Gated securely under the `sales.view_salesorder` permission.
* **Top Metric Bar**: Shows exact real-time tallies of confirmed orders, pre-orders, and drafts alongside total revenue calculated across active orders.
* **Action Modules**: Hosts detailed operational navigation cards, such as the master link leading to the paginated and searchable **Sales Order List** (`sales:sales-order-list`).

### 3. Glassmorphic UI/UX Layout Standards
Both the dashboard and the sales overview templates use unified modern styles matching the system UI rules:
* **Metrics Cards**: Styled via `.glass-card` and `.stat-card` wrappers, displaying currency values in monospaced format (`JetBrains Mono`).
* **Visual Polish**: Employs `.text-gradient` headers, Lucide icon accents, and glowing hover triggers using absolute-positioned `.card-bg-glow` radial gradients.

### 4. Efficient Database Aggregation
We calculate revenue values inside the database rather than loading models into memory. We use Django's `aggregate` engine with `Sum` and `F` expressions to sum up the requested quantity times unit price across all active items:
```python
total_revenue = SalesOrderItem.objects.filter(
    order__is_deleted=False
).aggregate(
    total=Sum(F('requested_qty') * F('unit_price'))
)['total'] or 0
```

## Consequences
* **Positive**: Clean separation of concerns between overall role hubs and specific domain landing pages.
* **Positive**: Zero performance lag under high order volumes due to optimized DB-level aggregations.
* **Positive**: Visual consistency with the application's glassmorphism style rules.
* **Negative**: Group names and permissions must be seeded properly (via `seed_groups`) for role-based gating to resolve successfully.
