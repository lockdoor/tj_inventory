# ADR 0010: Replenishment Round Unpost and Unlock Action

**Status:** Accepted  
**Date:** 2026-09-30  

## Context

In the petty cash workflow, replenishment rounds are finalized and locked for Express ERP posting via the "Lock & Mark as Posted" action in `PettyCashPaymentSummaryView`. Once locked, each `PettyCashPayment` has its `is_posted` attribute set to `True`, which restricts editing and cancellation of individual vouchers.

Previously:
- When all vouchers in a round were posted, the UI displayed:
  *"All vouchers for this round have been posted and locked."*
- There was no administrative mechanism to unlock or unpost vouchers in a replenishment round if corrections or adjustments needed to be made before reconciliation.
- Accountants had no way to revert a locked round without manually modifying database records.

## Decision

1. **Service Layer Method (`mark_payments_as_unposted`)**:
   Added `mark_payments_as_unposted(payments, *, user=None)` to [PettyCashPaymentService](file:///home/pnamnil/work/tj_inventory/django/srcs/accounting/services/payment_service.py). It atomically sets `is_posted = False`, `posted_at = None`, and `posted_by = None` for all active vouchers in the collection.

2. **View Action Support (`action == 'unlock'`)**:
   Updated `PettyCashPaymentSummaryView.post` to accept an `action` parameter (`'lock'` or `'unlock'`). When `action == 'unlock'`, it finds all posted payments in the selected round and calls `PettyCashPaymentService.mark_payments_as_unposted`.

3. **Summary Interface (`payment_summary.html`)**:
   - Added an **"Unlock & Mark as Unposted"** button with confirmation prompts when a round is fully locked.
   - Also provided the option to unlock previously posted vouchers if a round contains both posted and unposted transactions (e.g. when backdated vouchers are added after initial posting).

## Consequences

- Accountants and authorized users can safely reopen a locked replenishment round for editing or re-allocation.
- Complete audit trail preserved through SimpleHistory.
