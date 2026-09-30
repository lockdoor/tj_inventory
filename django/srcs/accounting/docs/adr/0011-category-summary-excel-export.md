# ADR 0011: Petty Cash Category Summary Excel Export ("ใบสรุปค่าใช้จ่ายตามหมวดบัญชี")

**Status:** Accepted  
**Date:** 2026-09-30  

## Context

In [ADR 0008](file:///home/pnamnil/work/tj_inventory/django/srcs/accounting/docs/adr/0008-payment-excel-export.md), we introduced an Excel export for itemized vouchers ("ใบเบิกเงินสดย่อย") enabling custodians to submit receipts for cash replenishment.

However, accountants and financial controllers responsible for entering GL journal entries in Express ERP also require an official, print-ready document summarizing **expenses aggregated by Chart of Accounts category**:
1. **Physical Audit Trail**: When filing petty cash reconciliations, accountants must attach a signed summary sheet reflecting the GL categories, VAT separation, rounding adjustments, and external PV records.
2. **Category Aggregations Card**: The `Category Aggregations` card in [payment_summary.html](file:///home/pnamnil/work/tj_inventory/django/srcs/accounting/templates/accounting/payment_summary.html) displayed this breakdown on screen, but had no button to export it as a print-ready document.

## Decision

We introduced a print-ready Category Summary Excel export:

1. **Reusable Aggregation Helper (`calculate_category_sums`)**:
   Extracted `calculate_category_sums(account, payments_qs)` in [payment_views.py](file:///home/pnamnil/work/tj_inventory/django/srcs/accounting/views/payment_views.py) to centralize category aggregation, VAT deduction, and rounding adjustments across both the HTML view and the Excel export.

2. **Dedicated Export View (`PettyCashCategorySummaryExportView`)**:
   - Registered endpoint at `/accounting/payments/account/<str:account_code>/summary/category-export/` named `'accounting:payment-summary-category-export'`.
   - Requires `accounting.view_pettycashpayment` permission.
   - Inherits multi-condition search filtering (`sf`, `sv`, `q`) and replenishment round resolution from `get_round_data`.

3. **Dedicated Excel Service (`PettyCashExcelExportService`)**:
   - Encapsulated openpyxl spreadsheet generation and formatting logic within `accounting/services/excel_service.py` (`PettyCashExcelExportService`).
   - Shared layout presets (A4 page setup, font styles, borders, fills) across both the replenishment claim vouchers export (`generate_replenishment_vouchers_excel`) and category summary export (`generate_category_summary_excel`).
   - Keeps views focused on HTTP request handling, permission validation, and parameter parsing.

4. **Print-Ready Document Layout**:
   - **Header Block**: Company name, Document Title (`"ใบสรุปค่าใช้จ่ายเงินสดย่อยตามหมวดบัญชี"`), Petty Cash Account name, and Replenishment date. When provided, the Express accounting PV number from the first item line of the replenishment voucher (`external_pv_no`) is included; otherwise it is left blank.
   - **Table Columns**:
     - `รหัสหมวดบัญชี` (Category Code)
     - `ชื่อหมวดหมู่ / รายการ` (Category Name): Clean Chart of Accounts category name only (e.g., `1155-00` displays `"ภาษีซื้อ-ยังไม่ถึงกำหนด"` without appended voucher/payee descriptions).
     - `ยอดเงิน (บาท)` (Total Amount, formatted `#,##0.00`)
   - **Total Row**: `รวมทั้งสิ้น` with dynamic `=SUM(C6:C{n})` formula and accounting double-underline border.
   - **Page Setup**: A4 portrait orientation (`ws.PAPERSIZE_A4`, `fitToWidth = 1`, `fitToHeight = 0`).

5. **UI Button Placement**:
   Placed an **"Export Excel"** button directly in the Category Aggregations card header of `payment_summary.html`, passing `round_id` and active search queries.

## Consequences

- Accountants can print an official, signed GL category summary for physical audit and filing with one click.
- Clean separation of concerns: views remain lean and easy to read while all Excel formatting logic lives in `PettyCashExcelExportService`.
- Single source of truth for category aggregation between UI and Excel export.
