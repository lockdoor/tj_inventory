# ADR 0007: Shortage Gating (Draft Lock) and Stable Shortage Record Reuse

## Status
Accepted (2026-05-27)

## Context
In our multi-sourcing allocation engine, customer demand lines are dynamically satisfied by physical stock lots (`STOCK`), scheduled arrivals (`ARRIVAL`), or dynamic shortages (`SHORTAGE`).
* **Sourcing vs. Fulfillment Mismatch**: Previously, dynamic shortages were considered a valid "allocation" strategy for item status, which allowed items to show "Fully Allocated" and allowed orders with outstanding shortages to transition to `PREORDER` status upon confirmation. This caused major operational confusion because WMS operators could see a validated order that physically could not be released or picked because it lacked stock.
* **Redundant Database Writes & PK Churn**: During every allocation refresh or manual sourcing override, the pending shortage record was physically deleted and recreated. This redundant write pattern churned database primary keys unnecessarily and caused shortage details deep-links/URLs (e.g. `/shortages/123/`) to break or change on every save, creating a poor user experience.

## Decision
We implement a clean refinement of our status workflow and shortage persistence layer.

### 1. Shortage is NOT a Fulfillment (Draft Status Gating)
We establish that shortages do not constitute fulfillment:
* **Item-level status**: If an item line has a shortage, it **cannot** show `Fully Allocated` (`allocated`). It must remain `Pending Allocation` or `Partially Allocated` depending on its physical/arrival coverage.
* **Order-level status**: A Sales Order with any outstanding shortage allocations is considered unfulfilled. It **MUST remain in `DRAFT` status** and cannot be confirmed as `CONFIRMED` or `PREORDER`. 
* **Dynamic Demotion**: If refreshing allocations on a `CONFIRMED` or `PREORDER` order generates any new shortage gaps, the order is dynamically **demoted back to `DRAFT` status** with a warning banner, locking it out of WMS picking releases until replenishment stock is verified.

### 2. In-Place Shortage Record Reuse & Stable Primary Keys
We optimize the sourcing persistence layer to reuse shortage records in both automatic and manual allocations:
* **Pending Shortage Lookup**: At the start of `refresh_allocation()`, we query any existing `PENDING` shortage record for that item line (matching order reference, reference type, and product SKU).
* **Bypass Purge**: During the allocation cleanup loop, we delete volatile `SalesAllocation` records, but we do **NOT** delete the underlying pending `Shortage` database record.
* **Update In-Place**: 
  - If a shortage gap still exists at the end of the waterfall sourcing engine, we **reuse the existing record** and update its quantity directly:
    ```python
    existing_shortage.request_qty = remaining_qty
    existing_shortage.save(update_fields=['request_qty', 'updated_at'])
    ```
    This keeps the shortage record completely stable, preserving its primary key `id` and deep-link URLs.
  - If the shortage gap is fully satisfied (resolved to `0`), we delete the shortage record cleanly.

## Consequences
* **Positive**: Absolute clarity in the sales-to-warehouse handoff: only orders with 100% secured stock (`CONFIRMED`) or secured future arrivals (`PREORDER`, with zero shortages) can be confirmed, preventing pick slip generation for shortages.
* **Positive**: Eliminates database primary key churn for shortage tables, keeping URLs and bookmarks stable for stock controllers.
* **Positive**: Unified service-layer logic simplifies the manual allocate and reset views since they no longer need to manage shortage creation or deletes directly.
