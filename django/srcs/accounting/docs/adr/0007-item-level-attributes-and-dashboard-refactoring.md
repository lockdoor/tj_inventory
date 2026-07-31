# ADR 0007: Item-Level Attributes, Granular Table Splitting, and Dashboard Refactoring

**Status:** Accepted  
**Date:** 2026-07-31  

## Context

After implementing ADR 0006, the workflow had some design limitations:
1.  **Restrictive Header Fields**: Storing `external_pv_no` and `rounding_adjustment` at the payment header level prevented multi-item payments from having separate external PV numbers or individual line rounding adjustments. It also introduced complexity by requiring rounding adjustments to be dynamically deducted from the payment's first item during summary calculations.
2.  **Lack of Item Visibility**: The main payments list and the replenishment summary tables rendered a single row per payment, hiding individual item descriptions, taxes, and amounts for multi-item vouchers.
3.  **Coarse Allocation Controls**: Accountants could only allocate an entire payment voucher to a category or PV, rather than allocating individual lines in a multi-item payment.
4.  **Cluttered Round Navigation**: The replenishment round selection dropdown in the summary view was difficult to navigate once a large number of rounds accumulated.
5.  **Hardcoded Dashboard**: The accounting dashboard overview used static layout cards unlike the cleaner, context-driven design in the inventory overview.

## Decision

We chose to migrate these configurations to a granular, item-level design:

1.  **Item-Level Model Migration**:
    *   Removed `external_pv_no` and `rounding_adjustment` from the `PettyCashPayment` header model.
    *   Added both fields to the `PettyCashPaymentItem` model, allowing each line item to track its own rounding and PV allocation.
    *   Created and applied Django migration `0005_remove_historicalpettycashpayment_external_pv_no_and_more.py` to update the PostgreSQL database.
2.  **Item-Level Allocation API**:
    *   Refactored `PettyCashPaymentAllocateAPIView` and updated the endpoint to `/accounting/items/<int:pk>/allocate/` to accept a line item ID.
    *   Accountants can now specify the category or external PV number for each item individually.
3.  **Granular Table Splitting**:
    *   Updated the shared `_payment_table.html` template to loop through all line items of each payment, rendering a separate row for each item.
    *   Individual rows display the item's local description, tax, rounding, and amount, and show the "Unposted" allocation button per-item.
4.  **Paginated Round Navigation**:
    *   Added "Older Round" and "Newer Round" pagination buttons to the replenishment summary view to easily step through rounds.
    *   Configured the selection dropdown to auto-submit on change, removing the need for a separate filter button.
    *   Displayed the total spent in the round at the top-right of the Category Aggregations card header.
5.  **Context-Driven Overview**:
    *   Refactored `PettyCashOverviewView` and `overview.html` to dynamically fetch dashboard module metrics and render them from view context, matching the design of the inventory dashboard.

## Consequences

### Positive
*   **True Multi-Item Support**: Single payment vouchers can now mix standard category allocations with lines allocated to separate external PVs or have individual rounding adjustments.
*   **Accurate Summary Aggregations**: Dynamic EOM calculations now aggregate item-level rounding values and calculate net spent (`amount - tax - rounding_adjustment`) precisely per line item.
*   **Intuitive UX**: The table split allows accountants to manage allocations per line item, and pagination simplifies stepping through historical rounds.
*   **Code Alignment**: Aligning the dashboard layout with the inventory module design makes codebase components consistent.
