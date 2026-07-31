# ADR 0006: EOM Summary Aggregates, External PVs, and Payment Rounding Adjustments

**Status:** Accepted  
**Date:** 2026-07-31  

## Context

After Renaming the app to `accounting` (ADR 0005), we needed to implement the core business logic for End of Month (EOM) posting, summary aggregations, and replenishment round calculations. Specifically:
1.  **VAT Separation**: Accountants require input VAT to be dynamically extracted from normal gross expenses and aggregated under a single undue input VAT code (e.g. `1155-00`) instead of being mixed into standard category expenses.
2.  **External Payment Vouchers (PV)**: Sometime accountants create PVs directly from external software (like Express ERP). These "actual PV" vouchers should bypass standard category allocation validation on EOM posting and be listed individually in the summary screen (using `PV: [external_pv_no]` as the category code) instead of being aggregated under standard category codes.
3.  **Voucher Redirection Callback**: Editing vouchers from the summary or detail pages should return the accountant back to the caller page using a redirection callback (e.g. `?next=...`).
4.  **Rounding Adjustments**: Custodians and accountants frequently round cash transactions (disbursements and adjustments) to integer values. The difference must be recorded under a rounding category code (e.g., `4200-07` or `4200-09`) to keep the cash box balance and ledger aligned.
5.  **Configurable Category Codes**: Different accounts or companies map tax and rounding adjustments to different Chart of Accounts (COA) codes. Hardcoding these codes is not viable.

## Decision

We chose to implement these requirements using a dynamic, non-splitting approach:

1.  **Configurable Codes on Account Model**:
    *   Added fields `vat_category_code` (defaults to `'1155-00'`) and `rounding_category_code` (defaults to `'4200-07'`) to the `PettyCashAccount` model.
2.  **Header-Level Rounding Adjustment**:
    *   Added a `rounding_adjustment` decimal field to `PettyCashPayment` to track positive or negative rounding values.
    *   Updated the UI form to dynamically show the rounding field for disbursements and adjustments using JavaScript.
    *   Calculated payment `total_amount` strictly as `sum(item.amount)` without adding rounding adjustment, treating the item amounts as gross/rounded.
3.  **Dynamic Summary Aggregates & First-Item Deduction**:
    *   Refactored `PettyCashPaymentSummaryView` to perform in-memory aggregation of normal expenses:
        *   Extracts VAT (`tax`) from items and sums them up under the account's configured `vat_category_code`.
        *   Deducts the payment's `rounding_adjustment` from the net amount calculation of the first item of each payment.
        *   Dynamically aggregates the sum of all rounding adjustments in the replenishment round under the account's configured `rounding_category_code`.
    *   This preserves a single line item in the database, avoiding formset edit/duplication bugs, while ensuring category sums balance exactly with the integer cash paid.
4.  **External PV Validation Bypass**:
    *   Updated EOM posting logic in `PettyCashPaymentService` to bypass category checks if a voucher has an `external_pv_no` assigned.
    *   Rendered actual PV records individually in the Category Aggregations table using `PV: [external_pv_no]`.

## Consequences

### Positive
*   **Database Integrity**: Standard payment vouchers retain a single clean line item rather than being artificially split into database rows for rounding, keeping the formset update workflow robust and simple.
*   **Multi-Company Support**: Companies like `TJ` and `JINTAN` can seamlessly use different codes (e.g. `4200-07` vs `4200-09`) for rounding adjustments via the account-level configuration.
*   **ERP Integration Safety**: External actual PVs are tracked and presented as unique rows, mirroring how they are handled inside the Express ERP.
