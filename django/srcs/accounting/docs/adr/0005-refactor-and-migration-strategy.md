# ADR 0005: Refactor `petty_cash` to `accounting` and Database Migration Strategy

**Status:** Accepted  
**Date:** 2026-07-18  

## Context

The `petty_cash` app was originally implemented as a standalone Django application. However, as the ERP system's scope expands, introducing multiple separate apps for other accounting contexts (like invoicing, billing, tax, and general ledger) would lead to "app bloat" and clutter the directory structure. 

To maintain a clean, modular, and scalable codebase, we decided to consolidate all finance-related functions inside a unified `accounting` domain. We also needed a migration strategy to handle the database schema change across local development, staging, and production environments.

## Decision

We chose to rename and transition the `petty_cash` module into the new `accounting` app using the following migration strategy:

1.  **Codebase Namespace Refactoring**:
    *   Renamed the directory from `django/srcs/petty_cash/` to `django/srcs/accounting/` using `git mv` to preserve commit history.
    *   Renamed the test files folder from `django/srcs/tests/petty_cash/` to `django/srcs/tests/accounting/`.
    *   Updated all Python imports, URL namespaces, template directory paths, and permission code references from `petty_cash` to `accounting`.

2.  **App Config & Settings Updates**:
    *   Replaced `'petty_cash'` with `'accounting'` in `INSTALLED_APPS` inside `settings.py`.
    *   Updated the main routing in `app/urls.py` to route `accounting/` urls to `accounting.urls`.

3.  **Database Migration Reset**:
    *   Since the petty cash module was in active development and did not contain any production business data, we chose **not** to lock the tables to legacy names using `db_table = 'petty_cash_...'`.
    *   We deleted the old `petty_cash` migration scripts and ran `makemigrations accounting` to create a fresh `0001_initial.py` migration script.
    *   This generates clean, standard Django table names prefixed with `accounting_` (e.g., `accounting_pettycashaccount` and `accounting_pettycashpayment`).

4.  **Database Table Cleanup**:
    *   To clean up database metadata, we executed a SQL script on all databases (local SQLite and production PostgreSQL) to drop the old, unused `petty_cash_*` and `petty_cash_historical*` tables:
        ```sql
        DROP TABLE IF EXISTS petty_cash_historicalpettycashpaymentattachment CASCADE;
        DROP TABLE IF EXISTS petty_cash_historicalpettycashpayment CASCADE;
        DROP TABLE IF EXISTS petty_cash_historicalpettycashaccount CASCADE;
        DROP TABLE IF EXISTS petty_cash_historicalpettycashcategory CASCADE;
        DROP TABLE IF EXISTS petty_cash_pettycashpaymentattachment CASCADE;
        DROP TABLE IF EXISTS petty_cash_pettycashpaymentitem CASCADE;
        DROP TABLE IF EXISTS petty_cash_pettycashpayment CASCADE;
        DROP TABLE IF EXISTS petty_cash_pettycashaccount CASCADE;
        DROP TABLE IF EXISTS petty_cash_pettycashcategory CASCADE;
        ```

## Consequences

### Positive
*   **Extensible Architecture**: The `accounting` app serves as a cohesive finance boundary. Future features (such as invoicing or general ledger modules) can be added as sub-modules directly inside `accounting/models/` and `accounting/views/` without creating new Django apps.
*   **Clean Database Metadata**: No legacy `petty_cash_` table names remain in the database schema.
*   **Zero Data Loss Impact**: Because the table rename was executed before actual business data was recorded in the database, the clean-slate migration was performed safely.
