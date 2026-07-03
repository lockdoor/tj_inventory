# ADR 0003: Bulk Express Chart of Accounts Sync and Hierarchical Display

**Status:** Accepted  
**Date:** 2026-07-03  

## Context

As legal entities (Companies) grow, their Chart of Accounts (ผังบัญชี) can easily contain over a thousand individual entries. Our initial category design had two major flaws:
1. **Performance Bottleneck**: Syncing categories from the Express bridge utilized loops of `update_or_create()` statements, causing hundreds of database round-trips and slow performance.
2. **Visual Clutter**: Displaying all companies' categories in a single flat list was overwhelming for users.

We needed a clean, scalable design that separates accounts by company, visualizes parent-child relationships (hierarchy), and provides millisecond-level bulk sync performance.

## Decision

We implemented a company-centric bulk synchronization and hierarchical visualization pattern:

1. **Bulk Database Sync**:
   Created `bulk_create_or_update_categories` inside `PettyCashCategoryService` utilizing Django's `bulk_create(..., update_conflicts=True)` command. This runs the sync in a **single database query**. It maps conflicts on the composite key `(company, code)` to update fields (`name`, `note`) and resets soft-delete indicators (`is_deleted=False`, `deleted_at=None`, `deleted_by=None`) to automatically restore items that exist in the active sync.

2. **Company-First List Index**:
   Refactored the main category list page to present a select company dashboard by default. Users can see the count of registered categories per company and trigger individual database syncs.

3. **Hierarchical Code Parsing**:
   Added a `@property def level(self)` helper to `PettyCashCategory` that computes the hierarchical depth (1 through 5) based on the format of the GL code:
   - Suffix `000-00` -> Level 1 (e.g., `1000-00`)
   - Suffix `00-00` -> Level 2 (e.g., `1100-00`)
   - Suffix `0-00` -> Level 3 (e.g., `1110-00`)
   - Suffix `-00` -> Level 4 (e.g., `1111-00`)
   - Any other suffix -> Level 5 (e.g., `1111-01`)

4. **Lightweight Collapsible Tree UI**:
   Implemented indent spacing in `category_list.html` mapped to the `level` property. Added a self-contained, native JavaScript `toggleChildren()` function that shows/hides descendants upon clicking parent `[+]`/`[-]` toggle buttons.

## Consequences

### Positive
* **Outstanding Performance**: Chart of Accounts syncs with thousands of rows now run in a single SQL operation.
* **Streamlined UX**: Users can view and search specific company charts without being overwhelmed by unrelated entities.
* **Visual Hierarchy**: The tree indentation mirrors the actual structure of the accounting ledger.
* **Automatic Restoration**: Synchronizing with active accounts automatically restores previously soft-deleted matching codes.
