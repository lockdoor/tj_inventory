# ADR 0008: Petty Cash Replenishment Excel Export Report ("ใบเบิกเงินสดย่อย")

**Status:** Accepted  
**Date:** 2026-09-21  

## Context

In the petty cash management workflow, after disbursements are recorded and a replenishment round is reviewed, custodians and accountants require an official physical document to request cash replenishment from finance or management.

This document, known in Thai accounting practices as **"ใบเบิกเงินสดย่อย"** (Petty Cash Replenishment / Reimbursement Claim Voucher), accompanies physical expense receipts and invoices.

Prior to this change:
1.  **Lack of Formatted Export**: The replenishment summary view (`payment_summary.html`) provided on-screen category aggregations and Express ERP posting controls, but offered no mechanism to export or print an official itemized requisition document.
2.  **Manual Compilation Required**: Users had to manually transcribe or retype voucher lines, payees, tax, and amounts into spreadsheets to produce a printable report for signature and audit.

## Decision

We introduced an automated, print-ready Excel export feature for replenishment rounds:

1.  **Export Button Placement**:
    *   Added an **"Export Excel"** button directly beneath the replenishment round select dropdown in the Filter Navigation Card (`payment_summary.html`).
    *   Preserved URL query parameters (`round_id`, `sf`, `sv`, `q`) in the export link, enabling users to export either the entire replenishment round or search-filtered transactions.
    *   Styled the button with an SVG spreadsheet icon and theme-compliant green accents (`#34d399`).

2.  **Export View (`PettyCashPaymentSummaryExportView`)**:
    *   Implemented a dedicated class-based view in `accounting/views/payment_views.py` inheriting from `LoginRequiredMixin`, `PermissionRequiredMixin` (`accounting.view_pettycashpayment`), and `View`.
    *   Registered the endpoint at `/accounting/payments/account/<str:account_code>/summary/export/` named `'accounting:payment-summary-export'`.
    *   Queried disbursements belonging to the selected round, excluding the replenishment top-up voucher itself.

3.  **Document Layout & Thai Accounting Standard Header**:
    *   **Header Row 1 (Merged A1:F1)**: Organization / Company display name (`account.company.name`), font 14pt bold, centered.
    *   **Header Row 2 (Merged A2:F2)**: Document title `"ใบเบิกเงินสดย่อย"`, font 13pt bold, centered.
    *   **Header Row 3 (Merged A3:F3)**: Replenishment date (`วันที่เบิกชดเชย: DD/MM/YYYY` or `วันที่เบิกชดเชย: รอบปัจจุบัน (ยังไม่ได้เบิกชดเชย)`), font 10pt italic, centered.
    *   **Row 4**: Blank separator.

4.  **6-Column Itemized Transaction Table (Row 5 onwards)**:
    *   `ลำดับ`: 1-based line item sequence number (centered).
    *   `วันที่`: Voucher payment date formatted as `DD/MM/YYYY` (centered).
    *   `จ่ายให้`: Payee name (left-aligned).
    *   `รายการ`: Detailed expense line item description (left-aligned).
    *   `ภาษี`: Item VAT/tax amount, formatted as `#,##0.00` (right-aligned).
    *   `ยอดเงิน`: Gross expense line amount, formatted as `#,##0.00` (right-aligned).

5.  **Summary Totals Row ("รวม")**:
    *   Merged columns A through D with label `"รวม"` (bold, right-aligned).
    *   Column E: Excel formula `=SUM(E6:E{n})` for total tax.
    *   Column F: Excel formula `=SUM(F6:F{n})` for total gross amount.
    *   Styled with standard accounting borders (thin top border, double bottom border).

6.  **Print & Page Configuration**:
    *   Configured sheet for A4 portrait orientation (`ws.PAPERSIZE_A4`, `ws.ORIENTATION_PORTRAIT`).
    *   Enabled `fitToWidth = 1` and `fitToHeight = 0` to prevent horizontal clipping when printed or converted to PDF.
    *   Specified calibrated column widths and row heights for clean visual balance.

## Consequences

### Positive
*   **Audit-Ready Printable Reports**: Users can generate a clean, official "ใบเบิกเงินสดย่อย" with a single click, ready for physical signing and filing.
*   **Dynamic Excel Formulas**: Using native Excel `=SUM(...)` formulas ensures totals remain accurate even if adjustments are made in the downloaded spreadsheet before printing.
*   **Filter-Aware Export**: Respects multi-field searches and filters, allowing users to generate targeted sub-reports when needed.
*   **No Additional Heavy Dependencies**: Utilizes the existing, well-supported `openpyxl` library.
