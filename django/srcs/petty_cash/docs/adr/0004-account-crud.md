# ADR 0004: Petty Cash Account CRUD and Security Constraints

**Status:** Accepted  
**Date:** 2026-07-03  

## Context

Petty Cash Accounts (cash boxes) require strict financial auditing. Modifying an account's custodian, altering its owner company, or directly mutating its cash balance manually after creation can break financial accountability trails and cause ledger discrepancies. We needed to design an Account CRUD module that is user-friendly yet strictly prevents dangerous mutations.

## Decision

We implemented a secure, service-validated CRUD workflow:

1. **Locking Custodian, Company, and Balance on Updates**:
   In `PettyCashAccountForm`, the `custodian`, `company`, and `balance` fields are marked as `disabled = True` during updates. This prevents form-level tampering. At the database/service layer, `PettyCashAccountService.update_account` enforces this rule by throwing a `ValidationError("Custodian can not update.")` if an update is attempted.

2. **Balance Mutation Control**:
   Cash balances can only be initialized on account creation. Any subsequent balance updates must flow through approved transaction workflows (vouchers/replenishments) in the service layer, rather than through direct form editing.

3. **Soft-delete Gating**:
   An account cannot be deleted (soft-deleted) if there are active (non-deleted) payment vouchers associated with it. This ensures transactional integrity.

4. **Explicit Choice Lists**:
   Since `currency` is stored as a standard `CharField` in the database for flexibility, the form explicitly declares a `ChoiceField` widget mapping supported options (`THB`, `USD`, `EUR`, `JPY`) to prevent empty selection menus.

## Consequences

### Positive
* **Auditable Integrity**: Custodians cannot bypass accountability by reassigning boxes or manually adjusting balances.
* **Orphan Prevention**: Accounts with active payments cannot be deleted until all transactions are cleared or cancelled.
* **Bilingual UI Options**: Clear select forms guide proper input configurations.
