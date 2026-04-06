# ADR 0004: Allow Negative Stock Balances

## Status
Accepted

## Context
Standard inventory systems often block transactions that would result in negative stock. However, for "pre-order" models or high-velocity environments, it may be necessary to complete outbound documents before the physical inbound shipment has been recorded in the system.

## Decisions
1.  **Remove Safety Locks**: Removed `ValidationError` checks in `complete_movement` and `revert_to_draft` that previously prevented balances from dropping below zero.
2.  **Mathematical Integrity**: The system continues to use `Decimal` for all calculations, ensuring that `-50.00` is recorded accurately as the stock balance.
3.  **Traceability**: Negative balances are clearly visible in the `StockCard` ledger, allowing for easy reconciliation when the missing stock is eventually received.

## Verification
-   Verified `test_outbound_completion_allows_negative_balance`: Deducting more than available results in a negative balance.
-   Verified `test_reversion_to_draft_allows_negative_balance`: Reverting an inbound that results in a negative balance is now permitted.
