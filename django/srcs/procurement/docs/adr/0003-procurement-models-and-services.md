# ADR 0003: Procurement Models and Services Implementation

## Status
Accepted

## Context
Following the minimalist scope defined in [ADR 0002](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/srcs/procurement/docs/adr/0002-implementation-plan-minimal-scope.md), we needed to implement the core data structures and business logic for tracking supply (Purchase Orders) and incoming shipments (Arrivals), along with a mechanism to track demand shortages.

## Decision
We have implemented a decoupled architecture within the `procurement` app, consisting of modular models and specialized services.

### 1. Model Architecture
Models are split into separate files under `procurement/models/` for maintainability:
- **`purchase_order.py`**: Contains `PurchaseOrder` and `PurchaseOrderItem`.
- **`arrival.py`**: Contains `Arrival` and `ArrivalItem`.
- **`shortage.py`**: Contains the `Shortage` model to bridge demand and supply.

**Key Design Points:**
- All header models inherit from `AuditableMixin` to ensure full audit trails (`created_by`, `versioning`, `soft_delete`).
- `ArrivalItem` maintains an optional link to `PurchaseOrderItem` to support partial fulfillment tracking.
- `Shortage` acts as a record for unfulfilled demand, allowing the Stock Controller to link it to specific Purchase Orders.

### 2. Service Layer
Business logic is encapsulated in `procurement/services/` to keep models thin and views clean:
- **`PurchaseOrderService`**: Manages PO lifecycles, status transitions (`DRAFT` -> `SUBMITTED` -> `CLOSED`), and atomic creation of POs with items.
- **`ArrivalService`**: Handles the scheduling and receiving of shipments, including updating quantities on receipt.
- **`ShortageService`**: Manages the creation and resolution of shortage records.

### 3. Verification
A comprehensive test suite was established in `tests/procurement/` covering:
- Model integrity and constraints (uniqueness, cascade deletes).
- Audit trail functionality.
- Service-level operations (atomic creation, status validation).

## Consequences
- **Positive**: High degree of modularity; business rules are centralized in services; full auditability of procurement actions.
- **Positive**: The system is ready to be integrated with the upcoming `preorder` app.
- **Negative**: Increased number of files compared to a monolithic `models.py` or `services.py`, but justified by the clarity of the domain boundaries.
