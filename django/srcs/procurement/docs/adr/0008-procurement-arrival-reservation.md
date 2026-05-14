# ADR 0008: Procurement Arrival Reservation

## Status
Accepted

## Context
In our "Triple-Ledger" reservation architecture, we need a way to commit stock that has not yet arrived in the warehouse (Future Stock). Customers often place "Sell Orders" for items that are currently in transit (Arrivals).

Without a dedicated ledger in the Procurement module, the system cannot:
1. Guarantee that incoming stock is allocated to the correct customer.
2. Prevent over-selling of expected quantities.
3. Provide the Stock Controller with visibility into how much of an incoming shipment is already "pre-sold".

## Decision
We will implement an **Arrival Reservation Ledger** within the Procurement app. This system mirrors the physical stock reservation logic but operates on `ArrivalItem` instead of physical `Stock`.

### Key Components:
1. **Model**: `ArrivalReservation` tracks the link between an `ArrivalItem` and a document (e.g., Sales Order).
2. **Synchronization**: `ArrivalItem` will maintain a `reserved_qty` field. This field is updated explicitly by the `ArrivalReservationService` whenever a commitment is modified.
3. **Validation**: All reservations must be validated against `ArrivalItem.expected_qty` to prevent commitments exceeding the shipment capacity.
4. **Reference Integrity**: Reservations include `reference_no` and `reference_type` to allow for precise bulk-management (e.g., clearing all locks when an order is cancelled).

## Consequences

### Positive:
- **Accuracy**: Real-time visibility into "Available-to-Promise" (ATP) quantities for incoming shipments.
- **Decoupling**: The Inventory app only handles physical stock, while the Procurement app handles future commitments.
- **Auditability**: Every future hold is explicitly recorded with a reference to the source document.

### Negative:
- **Synchronization Overhead**: Requires careful service-layer coordination to keep `reserved_qty` accurate.
- **Conversion Complexity**: When an `Arrival` is received, the system must eventually "promote" these future reservations into physical stock reservations (Handled in a separate logic block).

## Alternatives Considered
- **Universal Reservation Table**: Storing all reservations in one table. Rejected to keep domain boundaries clean and allow for different validation rules (Physical vs. Expected).
- **Signal-Based Sync**: Updating `reserved_qty` via post-save signals. Rejected in favor of explicit service calls for better transaction control and testability.
