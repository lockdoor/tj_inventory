# ADR 0005: Refactor StockCard to Single Quantity Field

## Status
Accepted

## Context
The initial `StockCard` implementation used dual columns (`qty_in`/`qty_out`). While clear for human-readable reports, this redundancy complicates data processing, aggregation, and future extensibility for other movement types (e.g., adjustments, returns, scrap).

## Decisions
1.  **Consolidate Fields**: Replaced `qty_in` and `qty_out` with a single `quantity` field and a `type` field.
2.  **Directional Semantic**: 
    -   `quantity`: Always stores the absolute (positive) magnitude of the change.
    -   `type`: `IN` (Added to stock) or `OUT` (Removed from stock).
3.  **Audit Reliability**: Reversals now explicitly record an `OUT` transaction for a reversed `IN`, ensuring a complete audit trail without needing to delete records.
4.  **Documentation**: Updated the `ERD.md` to ensure the project design remains in sync with the implementation.

## Verification
-   Verified `test_stockcard_creation` PASSED.
-   Verified `test_inbound_completion_with_multiple_same_lots` PASSED.
-   Verified `test_outbound_completion_allows_negative_balance` PASSED.
