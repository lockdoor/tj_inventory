# ADR 0005: Sales Order Document Attachments and Audited Soft-Deletion

## Status
Accepted (2026-05-26)

## Context
Sales transactions require supporting documentation (such as customer Purchase Orders, signed contracts, terms, or logistics invoices) to be permanently attached to the Sales Order record. Planners and Stock Controllers must be able to upload, download, and delete these files securely within their diagnostic dashboard.
* **Audit and Compliance Constraints**: To maintain perfect operational compliance and audit trials, supporting documents must never be physically hard-deleted. They must support soft-deletion, recording who deleted them and when, while immediately removing them from active user-facing dashboards.
* **Visual Excellence & Positioning**: The attachments interface must seamlessly align with the premium glassmorphism theme, rendered on the left sidebar of the Sales Order detail page directly above the **Audit Trail** card.
* **Accidental Deletion Protection**: Since these files contain critical financial and legal records, the deletion action must be safeguarded from accidental click triggers via double-opt-in verification.

## Decision
We implement a high-fidelity **Sales Order Attachments** feature utilizing the unified `AuditableMixin` soft-delete pattern, secure upload/delete handlers, a custom validation modal, and comprehensive integration testing.

### 1. Unified Audit and Model Structure (`sales/models/attachment.py`)
Created the `SalesOrderAttachment` model inheriting from `AuditableMixin` to capture full creation, soft-deletion, and versioning attributes:
- `sales_order` (ForeignKey linking to `SalesOrder` with `CASCADE` delete).
- `document_file` (FileField storing in a version-segregated directory `sales/so/%Y/%m/`).
- `file_name` (Automatically extracts `document_file.name` on `save` if not explicitly specified).
- `note` (Optional remark description).

### 2. Audited Upload and Soft-Delete Handlers (`sales/views/attachment_views.py`)
- **`SalesOrderAttachmentUploadView`**: POST view gated securely under the `'sales.change_salesorder'` permission. Binds the upload form, stamps auditing attributes (`created_by` and `updated_by`), and persists the transaction.
- **`SalesOrderAttachmentDeleteView`**: POST view gated under the `'sales.change_salesorder'` permission. Invokes `attachment.delete(user=request.user)` to run the soft-deletion (setting `is_deleted = True`, `deleted_at = timezone.now()`, and recording `deleted_by = user`).
- Registered routing under `orders/<int:pk>/attachment/upload/` and `orders/attachment/<int:pk>/delete/` in `sales/urls.py`.

### 3. Soft-Deletion UI Filtering
To ensure soft-deleted records are completely hidden in template rendering:
- Configured `SalesOrderDetailView.get_context_data` to fetch active records strictly via:
  ```python
  context['attachments'] = order.attachments.filter(is_deleted=False)
  ```

### 4. Premium Sidebar Card & Accidental Deletion Modal (`sales_order_detail.html`)
- **Supporting Documents Card**: An elegant glassmorphic sidebar card rendered directly above the Audit Trail card. Contains Lucide-style PDF icons, truncated text wrappers with hover-states, description note blocks, and a gated upload button.
- **Filename typing double-opt-in confirmation modal**: Clicking remove triggers a full-screen blurred modal dialog. It displays the targeted file name and **disables the submit button** until the user types the exact filename string into a monospace confirmation input field.

### 5. Automated Verification (`tests/sales/test_sales_detail_views.py`)
Added two exhaustive unit tests:
- `test_sales_order_attachment_upload_success`: Assures file binary chunks are saved correctly and attributes are pre-populated.
- `test_sales_order_attachment_delete_success`: Assures calling the delete view executes soft-deletion, verifying `is_deleted` becomes `True` while leaving the audit record in the database.

## Consequences
* **Positive**: Absolute document tracking compliance and historic audit capability for all Sales Orders.
* **Positive**: Beautiful visual layout continuity with glassmorphic cards and modal micro-animations.
* **Positive**: Accidental deletions are completely eliminated via filename typing verification.
* **Negative**: Requires disk storage for uploaded media assets (mitigated by media directory file exclusions in `.gitignore`).
