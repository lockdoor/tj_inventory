# ADR 0013: Sales Order Detail and Sourcing Allocations Diagnostics Architecture

## Status
Accepted

## Context
When Sales Orders are created in the system, they undergo a waterfall allocation process (Smart Sourcing) linking customer demand to specific sources (Actual stock, Incoming Arrivals, or Shortages).

Planners and Stock Controllers require a centralized, high-fidelity **Sales Order Detail view** to monitor order progress, analyze sourcing diagnostics (identifying which items are on-hand, incoming, or experiencing shortage gaps), and manually re-allocate items once new stock becomes available or incoming shipments are scheduled.

## Decision
We implemented the Sales Order Detail view and the interactive Sourcing Allocations Diagnostic panel using the following design and architecture decisions:

### 1. Database Optimization & Pre-fetching
To render the nested items and sourcing allocations hierarchy efficiently without triggering N+1 database queries, `SalesOrderDetailView` preloads all relation paths:
```python
def get_queryset(self):
    return SalesOrder.objects.filter(is_deleted=False).select_related(
        'partner',
        'created_by',
        'updated_by'
    ).prefetch_related(
        'items__item',
        'items__allocations__physical_reservation__stock__warehouse',
        'items__allocations__arrival_reservation__arrival_item__arrival__warehouse',
        'items__allocations__shortage'
    )
```

### 2. Interactive "Refresh Allocations" Engine Trigger
To allow planners to manually re-run the smart allocation gap-filler after recording procurement expected dates, receiving arrivals, or registering new stock lots, we created a POST-only endpoint `SalesOrderRefreshAllocationView`:
- Gated under the `sales.change_salesorder` permission.
- Iterates over all order items and executes the transactional auto-sourcing gap-filler: `SalesService.refresh_allocation(item)`.
- Protects void/completed records by immediately returning an error if the sales order status is `cancelled` or `shipped`.

### 3. Integrated Diagnostics Panel and Cross-Module Deep-Linking
In `sales_order_detail.html`, each ordered item displays a diagnostic sourcing allocations block showing exactly where quantities are pulled from:
- **Physical Stock (Stock)**: Renders warehouse codes and lot numbers.
- **Incoming Arrival (Arrival)**: Provides a clickable link directly to the Procurement Arrival details page (`procurement:arrival-detail`) so planners can inspect inbound schedules.
- **Recorded Shortages (Shortage)**: Provides a clickable link directly to the Procurement Shortage details page (`procurement:shortage-detail`), displaying the active state of the shortage gap (e.g., Pending, PO Created, Cancelled) to trace the procurement pipeline status in real-time.

## Consequences

### Positive:
- **Cross-Module Transparency**: Linking shortages directly to their procurement details page and arrivals directly to their arrival schedules connects Sales and Procurement seamlessly, giving planners full visibility into the supply chain.
- **Dynamic Re-Allocation**: Planners can resolve shortages instantly with a single click once new stock is added or arrivals are registered.
- **Excellent Performance**: Optimized database query paths preload all nested tables in a single transaction, keeping load times lightning-fast.

### Negative:
- The `is_manual` flag must be set to `True` on manually picked stock lines to protect them from being overwritten during a smart allocation refresh (a necessary constraint to honor customized packaging/lot choices).
