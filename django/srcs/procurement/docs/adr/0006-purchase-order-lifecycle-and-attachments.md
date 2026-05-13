# ADR 0006: Purchase Order Lifecycle, Service Refactor, and Attachments

## Status
Accepted

## Context
After implementing the basic Purchase Order (PO) creation and list views, the system required a more robust lifecycle management (Status transitions), a polished detail view for inspection, and the ability to attach supporting documents (Invoices, Packing Lists). Additionally, to maintain project standards, the logic initially implemented in views needed to be refactored into the service layer.

## Decision
We have finalized the Purchase Order management module by implementing lifecycle controls, a high-fidelity UI, and a generic attachment system.

### 1. Purchase Order Lifecycle & Detail View
- **Status Transitions**: Implemented secure transitions between `DRAFT` and `SUBMITTED` status.
- **Reversion**: Added "Revert to Draft" capability for `SUBMITTED` orders to allow corrections before final closure.
- **Detail UI**: Created a premium glassmorphism template ([`purchase_order_detail.html`](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/templates/procurement/purchase_order_detail.html)) that mirrors the layout of the Inventory module, providing a consistent user experience.

### 2. Service Layer Refactor
To ensure thin views and reusable business logic, we moved all operational logic from `views.py` to [`PurchaseOrderService`](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/services/purchase_order_service.py):
- Centralized status validation and atomic saving.
- Implemented `sync_items` logic to handle complex line-item updates (create/update/delete) during PO modification.
- Standardized `ValidationError` handling to surface business rule violations in the UI.

### 3. Supporting Documents (Attachments)
Implemented a modular attachment system for both Purchase Orders and Arrivals:
- **Models**: Added `PurchaseOrderAttachment` and `ArrivalAttachment` in [`attachment.py`](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/models/attachment.py).
- **Capability**: Supports uploading various file formats (PDF, images, spreadsheets) with automatic metadata tracking.
- **UI**: Integrated an upload/delete interface directly into the PO Detail view, restricted to `DRAFT` status for data integrity.

### 4. Database Schema Update
- Updated the **Procurement ERD** to reflect the new attachment models.
- Applied migrations to establish the new tables and relationships.

## Consequences
- **Positive**: Consistent UX across Inventory and Procurement modules.
- **Positive**: Strict enforcement of business rules via the Service Layer.
- **Positive**: Improved audit compliance by allowing digital storage of physical documents alongside digital records.
- **Positive**: The system is now ready for the **Arrival Integration** phase, where POs will be fulfilled by incoming shipments.
