# ADR 0016: External Express ERP Stock Cross-Check Architecture

**Status:** Accepted  
**Date:** 2026-04-28  

## Context

TJ Inventory serves as the modern, real-time warehouse management system. However, the company continues to rely on a legacy Windows-based system (Express ERP) as the official financial ledger. The Express ERP data is stored in legacy `.DBF` database files (specifically `STLOC.DBF` and `STMAS.DBF`).

A critical operational requirement is the ability to perform a **Stock Cross-Check (Reconciliation)** to ensure that the physical stock levels recorded in Django exactly match the official financial ledger in Express ERP. 

Initially, the Django application attempted to mount and read these `.DBF` files directly over a network file share (SMB/NAS). This approach proved brittle, leading to jittery network connection issues, file lock conflicts, and performance bottlenecks.

## Decision

To resolve the network and architectural friction, we implemented a decoupled HTTP Bridge architecture and a dedicated Django reconciliation service:

1. **Standalone FastAPI Bridge:** 
   We created a lightweight Python FastAPI application (`express/main.py`) designed to run directly on the host machine containing the Express `.DBF` files. This bridge securely reads the local database files (ignoring missing memo files to prevent crashes) and exposes the data via a fast, reliable REST API (`GET /stock/{company_id}`). It specifically filters for `LOCCOD = '01'` (Stock 1) to match our reconciliation requirements.

2. **Django `ExpressService` API Client:**
   The Django backend was refactored to consume the FastAPI bridge. The `ExpressService.get_express_balances` method now executes an HTTP `GET` request using the `requests` library, returning a clean JSON list of items and their balances.

3. **Dynamic Warehouse Mapping:**
   Since an Express "Company" (e.g., `TJ`, `THAIJINTAN`) maps to a specific internal Django "Warehouse" (e.g., `TG001`, `TJ001`), we externalized this configuration to environment variables (`COMPANY_WAREHOUSE_CODES`). This allows dynamic routing without hardcoding business logic.

4. **Strict Targeted Comparison Logic:**
   In `ExpressService.get_comparison_data()`, the reconciliation logic:
   - Fetches the mapped internal Django warehouse code.
   - Aggregates non-zero stock lot balances strictly for that target warehouse (`warehouse__code=target_wh_code`).
   - Filters the master item catalog (`catalog.models.Item`) to strictly loop over items that possess a stock relationship with that target warehouse (`stocks__warehouse__code=target_wh_code`).
   - Compares the resulting Django quantities against the Express Bridge quantities, calculating the exact mathematical variance.

5. **Dedicated UI Integration:**
   We introduced `comparison_views.py` (`StockComparisonListView`) and `stock_comparison.html`. Buttons were added directly to the primary "Physical Stock Balances" dashboard allowing users to instantly trigger a cross-check for any configured Express entity.

## Consequences

### Positive
* **Reliability:** HTTP requests are stateless and significantly more reliable than maintaining active network file mounts to a legacy Windows system.
* **Performance:** The FastAPI bridge reads local files quickly and transmits minimal JSON payloads over the network.
* **Accuracy:** By strictly isolating comparisons to specific warehouse mappings, we eliminated "ghost" variances (where an item existed in the master catalog but had no business being in a specific warehouse).
* **User Experience:** Warehouse administrators can now perform real-time financial ledger audits directly from the modern Django glassmorphism UI with one click.

### Negative
* **Operational Overhead:** We must now deploy, monitor, and maintain a secondary microservice (the FastAPI bridge) on the Windows legacy host.
* **Eventual Consistency:** The data is pulled on-demand. If Express ERP is modified concurrently while the dashboard is loading, slight race conditions could occur, though this is acceptable for audit workflows.
