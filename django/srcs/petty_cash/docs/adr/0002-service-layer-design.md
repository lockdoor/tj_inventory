# ADR 0002: Service Layer for Petty Cash Management

**Status:** Accepted  
**Date:** 2026-07-02  

## Context

To handle cash balance updates safely, prevent financial race conditions, enforce company-specific accounting validation rules, and ensure clean separation of concerns, we needed to implement a robust service layer for the `petty_cash` app.

The design must enforce transaction row-locking on account balances during updates, protect the system against negative balances (insufficient funds), restrict direct modifications that breach audit trails, and keep views light and focus-driven.

## Decision

We designed and built the Petty Cash service layer using isolation patterns, atomic transactions, database locks, and strict validation checks:

1. **Service Separation**:
   Divided mutations into three dedicated services:
   - `PettyCashCategoryService` ([category_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/petty_cash/services/category_service.py))
   - `PettyCashAccountService` ([account_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/petty_cash/services/account_service.py))
   - `PettyCashPaymentService` ([payment_service.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/petty_cash/services/payment_service.py))

2. **Concurrency Protection (`select_for_update`)**:
   Updating a cash box balance requires row-level locking. In `PettyCashPaymentService.create_payment()`, `update_payment()`, and `cancel_payment()`, we fetch the account using `select_for_update()` inside a `transaction.atomic` block to block concurrent operations until the balance reconciliation completes.

3. **Financial Updates Support (Option 3)**:
   We implemented an `update_payment` method that allows full financial updates to a voucher:
   - Compares the new item lines total against the old total to find the difference (`diff`).
   - Reconciles the account balance (adding or subtracting the `diff`).
   - Employs a **Negative Balance Guard**: if the update causes the account balance to fall below zero, it throws a `ValidationError` and rolls back the database transaction.
   - Cleans and regenerates the associated payment lines.

4. **Custodian Change Limitation (Option B)**:
   In `PettyCashAccountService.update_account()`, we raise a `ValidationError("Custodian can not update.")` if a user attempts to change the custodian of an existing cash account. To change a custodian, the old cash box must be inactivated and a new one opened.

5. **Referential Integrity on Deletions**:
   - Categories cannot be soft-deleted if referenced by active payment items.
   - Accounts cannot be soft-deleted if they contain active payments.

## Consequences

### Positive
* **Concurrency Safety**: Account balances are safe from multi-threaded race conditions.
* **Audit Trail Security**: Custodians cannot be changed on historic accounts, ensuring all past vouchers match the responsible party.
* **Granular Validation**: Validates that all category GL codes align with the account's company before any balance mutations occur.
* **Consolidated Business Rules**: View layer remains simple as all validation, locking, and math resides in the services.
