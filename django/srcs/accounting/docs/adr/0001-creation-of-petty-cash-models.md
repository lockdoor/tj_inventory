# ADR 0001: Creation of Petty Cash Models

**Status:** Accepted  
**Date:** 2026-07-02  

## Context

To manage internal cash funds, track disbursements, replenishments, and adjustments, and integrate seamlessly with our central multi-tenant `Company` and bilingual `Individual` models, we needed to implement the core database schema for the new `petty_cash` application.

The design must enforce strict auditing rules (tracking who made or altered entries), preserve referential integrity, support company-specific accounting (ผังบัญชี) mappings, and keep document header/line logic highly cohesive.

## Decision

We defined and implemented five models grouped inside a modular `models` package directory, matching the design of the centralized [ERD](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/petty_cash/docs/ERD.md):

1. **`PettyCashCategory`** ([category.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/petty_cash/models/category.py)):
   Binds expense categories and general ledger (GL) account codes to a specific legal entity (`Company`). Implements a unique together constraint on `company` + `code` to support multi-company account mappings (e.g., Express accounting imports).

2. **`PettyCashAccount`** ([account.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/petty_cash/models/account.py)):
   Represents physical or virtual cash boxes. Restricts deletion using `models.PROTECT` on the owner `Company` and assigned `custodian` (User) fields.

3. **`PettyCashPayment` & `PettyCashPaymentItem`** ([payment.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/petty_cash/models/payment.py)):
   - Declared both models in the same file to keep document logic highly cohesive.
   - `PettyCashPayment` represents the transaction header. It supports both registered profiles (foreign key to `Individual` in outer common context) and unregistered direct text values in `payee_name`.
   - Overrides `save()` on `PettyCashPayment` to auto-generate unique sequential voucher reference codes (e.g. `PV-YYYYMMDD-XXXX`) if not explicitly specified.
   - `PettyCashPaymentItem` represents detailed voucher line distributions, each referencing a company-specific category code.

4. **`PettyCashPaymentAttachment`** ([attachment.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/petty_cash/models/attachment.py)):
   Handles supporting documents (receipt files) with date-based upload subdirectories (`petty_cash/attachments/%Y/%m/`), keeping file assets organized.

5. **Auditing Mixin Integration**:
   Inherited `AuditableMixin` on categories, accounts, payments, and attachments to log creation times, editors, version counters, and soft-delete states (`is_deleted`).

## Consequences

### Positive
* **Cohesive Code Layout**: Placing items and header models in `payment.py` makes relations easier to read and maintain.
* **Audit Compliance**: Inheriting `AuditableMixin` ensures every cash box adjustment and voucher has a complete audit trail.
* **Accounting Integration Ready**: Mappings are structured to allow exports to external systems (like Express Program) based on company-specific categories.
* **Safe Referencing**: Deletion guards (`on_delete=models.PROTECT`) prevent deleting active companies or custodians that currently manage open cash funds.
