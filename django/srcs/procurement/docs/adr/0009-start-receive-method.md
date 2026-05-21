# ADR 0009: Start Receiving Flow with Custom Quantities and Role-Based Permissions

## Status
Accepted

## Context
In our initial implementation, the "Start Receiving" action on an Arrival record automatically generated a draft Inventory Movement using the full expected quantities defined during the scheduling phase. 

However, in physical logistics, the actual delivered quantities frequently deviate from the expected amounts due to supplier shipping errors, damaged items, or partial fulfillments. Hardcoding the expected quantities into the movement required manual adjustments after movement generation, which was error-prone and counter-intuitive.

Furthermore, initiating stock receiving is a highly sensitive operational activity that physically updates warehouse ledger drafting. While a **Stock Controller** is responsible for creating and scheduling arrivals, the execution of the physical receiving process belongs strictly to the **Warehouse Admin**. The system needed clear boundaries to enforce this segregation of duties.

## Decision
We have implemented a customizable **Start Receiving** flow that combines frontend interactive modals, flexible service-layer methods, and strict role-based permission checks.

### 1. Flexible Service Layer (`ArrivalService.initiate_receiving`)
- Updated the service method to accept an optional dictionary `receive_quantities` mapping `ArrivalItem` IDs to actual decimal values.
- Converts actual package unit quantities using item packaging multipliers before creating inventory movement lines.
- Computes correct unit costs based on the adjusted quantities and automatically structures Lot numbers in the format `LOT-<sku>-<expiry_date_or_pending>`.

### 2. Premium Three-Field Modal Interface
- Implemented a slate-glass modal overlay (`#start-receiving-modal`) on the Arrival Detail view.
- To keep the modal simple and focused, it displays exactly three fields:
  1. **Product Name** (Product title, SKU, packaging type).
  2. **Expected Qty** (Expected quantity from schedule).
  3. **Receive Qty** (Editable number input field initialized with the expected quantity).
- Built keyboard accessibility (closes immediately on `Escape` keypress).

### 3. Strict Segregation of Duties and Role-Based Permissions
To properly divide operational planning from stock execution, we restructured the dashboard and templates:
- **Dashboard Separation**: 
  - The "Arrival Schedules" module card has been removed from the Stock Controller dashboard and added to the **Warehouse Admin** dashboard to act as their primary receiving hub.
- **Logistics Schedule Ownership**:
  - The "Edit Schedule" button on scheduled Arrivals is restricted only to members of the `stock_controller` group via the context check `is_stock_controller`.
- **Start Receiving Authorization**:
  - Restricts visibility of the "Start Receiving" button on the Arrival detail page strictly to members of the `warehouse_admin` group (and superusers) using the `is_warehouse_admin` boolean flag.
  - The backend view (`ArrivalReceiveActionView`) strictly rejects POST requests from any user who is not a superuser or member of the `warehouse_admin` group, redirecting them with an error notification.
- **Django Native Permission Mapping**:
  - Seeded the `warehouse_admin` group with standard Django permissions `'procurement.view_arrival'` and `'procurement.change_arrival'` in `seed_groups.py`. This ensures they can access the detail page and POST to the receive action while maintaining Django's native authentication flow.

## Consequences

- **Positive**: **Real-World Alignment**: Warehouse staff can enter exactly what arrived on the truck directly inside the flow, generating an accurate draft Inventory Movement immediately.
- **Positive**: **Robust Security**: Prevents unauthorized users (like Sales Representatives or Stock Controllers) from initiating or modifying physical stock-in activities, reducing internal shrinkage risk.
- **Positive**: **Clean Segregation**: Keeps scheduling and editing with the Stock Controller, while execution and dashboard tracking lie with the Warehouse Admin.
- **Positive**: **Automated Lot Structure**: Improves warehouse traceability by automatically naming lots with lot numbers embedded with expiration dates.
