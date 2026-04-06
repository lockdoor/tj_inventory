# ADR 0003: Movement Completion and Reversal Logic

## Status
Completed (Initial Implementation)

## Context
Inventory movements begin as drafts and must be "Completed" to affect physical stock. Once completed, they should also be reversible to "Draft" to allow corrections, provided safety rules are met.

## Decisions
1.  **Completion Logic**:
    -   Processes all items in a single atomic transaction.
    -   Uses `select_for_update()` to lock `Stock` records and ensure accurate cumulative balance updates for the same LOT.
    -   Generates a `StockCard` audit entry with the note: `[COMPLETION]: Movement <DOC_NO>`.
2.  **Reversion Logic**:
    -   Inverts stock updates and generates `[REVERSION]` StockCards.
    -   **Initial Safety Rule**: All transactions must result in a `balance >= 0`. (Note: This rule is updated in ADR 0004).
3.  **Audit Integrity**: Every stock change is linked to its source `InventoryMovementItem` through the `StockCard` ledger.

## Verification
-   Verified cumulative LOT handling in inbound completion.
-   Verified outbound stock security (initially blocked if insufficient).
-   Verified reversal safety blocks.
