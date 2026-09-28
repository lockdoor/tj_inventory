# ADR 0009: Chronological Replenishment Round Query by Payment Date

**Status:** Accepted  
**Date:** 2026-09-28  

## Context

In the petty cash management workflow, transactions are segmented into periodic cycles termed **"Replenishment Rounds"**. Each round represents expenses incurred from the previous replenishment up to the current replenishment top-up voucher.

Prior to this decision:
1. **Primary Key ID-Based Filtering**: The round filtering logic in `PettyCashPaymentSummaryView` and `PettyCashPaymentSummaryExportView` segmented vouchers strictly using database primary keys (`PettyCashPayment.id`):
   ```python
   # Old implementation
   payments_qs.filter(id__gt=prev_rep.id, id__lte=selected_rep.id)
   ```
2. **Backdated Voucher Omission**: In real-world accounting workflows, receipts and vouchers are frequently entered retroactively or recorded after a replenishment voucher has already been drafted or entered into the system. Under ID-based filtering, any voucher created after a replenishment received an auto-increment `id` greater than the replenishment (`voucher.id > replenishment.id`). Consequently, even if its actual `payment_date` occurred before the replenishment date, it was omitted from the intended round and mistakenly pushed into the Active (Unreplenished) round.
3. **Inconsistent Ordering and Boundary Definition**: While the replenishment dropdown options were sorted chronologically (`-payment_date, -id`), the previous replenishment boundary (`prev_rep`) was queried by `id__lt=selected_rep.id`, creating inconsistencies whenever replenishments were created out of chronological sequence.
4. **Code Duplication Across Views**: The round-resolution and voucher-filtering logic was independently duplicated in three locations:
   - `PettyCashPaymentSummaryView.get_context_data` (Summary display)
   - `PettyCashPaymentSummaryView.post` ("Lock & Mark as Posted" action)
   - `PettyCashPaymentSummaryExportView.get` (Excel requisition export)

## Decision

We transitioned replenishment round boundary querying from database `id` sequence to **chronological transaction date (`payment_date`)** with primary key tie-breaking, and centralized the logic into a unified helper function:

1. **Unified Helper (`get_round_data`)**:
   Extracted `get_round_data(account, round_id=None)` in `accounting/views/payment_views.py` to serve as the single source of truth for round resolution across summary, lock, and export endpoints.

2. **Chronological Boundary Resolution (`payment_date, id`)**:
   - **Previous Replenishment (`prev_rep`)**:
     Identified by finding the replenishment immediately preceding `selected_rep` chronologically:
     ```python
     prev_rep = replenishments.filter(
         Q(payment_date__lt=selected_rep.payment_date) |
         Q(payment_date=selected_rep.payment_date, id__lt=selected_rep.id)
     ).order_by('-payment_date', '-id').first()
     ```
   - **Round Voucher Query**:
     Vouchers belonging to `selected_rep` must satisfy:
     - Strictly after `prev_rep`: `payment_date > prev.payment_date OR (payment_date == prev.payment_date AND id > prev.id)`
     - Up to and including `selected_rep`: `payment_date < current.payment_date OR (payment_date == current.payment_date AND id <= current.id)`
     ```python
     if prev_rep:
         payments_qs = payments_qs.filter(
             (Q(payment_date__gt=prev_rep.payment_date) | Q(payment_date=prev_rep.payment_date, id__gt=prev_rep.id)) &
             (Q(payment_date__lt=selected_rep.payment_date) | Q(payment_date=selected_rep.payment_date, id__lte=selected_rep.id))
         )
     else:
         payments_qs = payments_qs.filter(
             Q(payment_date__lt=selected_rep.payment_date) |
             Q(payment_date=selected_rep.payment_date, id__lte=selected_rep.id)
         )
     ```
   - **Active (Unreplenished) Round**:
     Encompasses all vouchers after the latest replenishment chronologically:
     ```python
     active_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False).filter(
         Q(payment_date__gt=latest_rep.payment_date) |
         Q(payment_date=latest_rep.payment_date, id__gt=latest_rep.id)
     )
     ```

3. **Same-Day Tie-Breaking**:
   Using composite `(payment_date, id)` comparisons ensures deterministic segmentation when multiple transactions or replenishments occur on the exact same date without missing or duplicating vouchers.

4. **Integration Across All Consumer Views**:
   Refactored `PettyCashPaymentSummaryView.get_context_data`, `PettyCashPaymentSummaryView.post`, and `PettyCashPaymentSummaryExportView.get` to consume `get_round_data`.

## Consequences

### Positive
* **Accounting Domain Alignment**: Backdated vouchers correctly appear in the replenishment round corresponding to their transaction date, matching user expectations.
* **Elimination of Sequence Discrepancies**: Users can enter missing receipts at any time without vouchers being orphaned into future rounds simply due to late record entry.
* **DRY & Maintainable**: Single helper function prevents divergence between the UI summary, Express ERP locking action, and Excel report export.
* **Deterministic Boundary Handling**: Same-day replenishments and vouchers are cleanly handled without boundary gaps.

### Considerations
* **Backdated Entries in Locked Rounds**: If a voucher is backdated into an already locked/posted round, it will appear as an unposted voucher in that round's summary. This accurately informs accountants that an unposted transaction exists that requires reconciliation or posting to Express ERP.
