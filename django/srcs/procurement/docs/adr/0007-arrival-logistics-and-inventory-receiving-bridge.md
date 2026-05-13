# ADR 0007: Arrival Logistics and Inventory Receiving Bridge

## Status
Accepted

## Context
Following the successful implementation of the Purchase Order (PO) module, the system needed a mechanism to track the physical delivery of ordered goods. This phase requires bridging the gap between "ordered" status in Procurement and "on-hand" status in Inventory.

## Decision
We have implemented the **Arrival Module**, which acts as the logistics intermediary between Purchase Orders and Inventory Movements.

### 1. Logistics-Focused Data Model
- **Arrival Model**: Tracks scheduled shipments, expected dates, and destination warehouses.
- **Arrival Items**: Linked to specific PO line items (`po_item`) to track partial or full fulfillment of orders.
- **Attachments**: Integrated the attachment system to allow storing delivery notes, packing lists, or photos of received goods.

### 2. Automated Procurement Workflow
To reduce manual data entry and errors, we implemented several automation features:
- **PO-to-Arrival Bridge**: A "Schedule Arrival" action from the PO detail page pre-fills the arrival form with relevant order data.
- **Dynamic Selection**: Implemented a JSON API (`PurchaseOrderItemsAPIView`) and client-side logic to automatically fetch and populate item lines when a Source PO is selected in the arrival form.
- **Business Rule Enforcement**: Arrivals can only be scheduled for `SUBMITTED` Purchase Orders.

### 3. The Inventory Receiving Bridge
The core value of the module is the atomic link to the Inventory system:
- **Initiate Receiving**: Created a service method (`ArrivalService.initiate_receiving`) that generates a `DRAFT` `InventoryMovement` from an Arrival record.
- **Data Continuity**: Maintains the `reference_no` and `reference_type` audit trail from PO -> Arrival -> Movement, ensuring traceability from procurement to the physical shelf.

### 4. UI/UX and Dashboard Integration
- **Glassmorphism Design**: Applied the project's premium design system to list, detail, and form views for Arrivals.
- **Dashboard Card**: Added an "Arrival Schedules" card to the Stock Controller Command Center for quick access to logistics status.

## Consequences
- **Positive**: Eliminates redundant data entry by pulling items directly from orders.
- **Positive**: Provides a clear distinction between "scheduling a shipment" and "physically receiving stock".
- **Positive**: Strict data integrity is maintained between procurement and inventory modules through the service layer.
- **Positive**: Improved warehouse readiness, as staff can see scheduled arrivals before the truck arrives.
- **Negative**: Adds complexity to the procurement lifecycle (PO -> Arrival -> Movement), but this reflects real-world supply chain needs.
