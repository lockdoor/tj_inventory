# ADR 0011: Cross-Domain Traceability via Movement References

## Status
Accepted

## Context
As the project grows, warehouse movements will increasingly be triggered by external business events (e.g., a Production Run finishing, a scheduled Stock Arrival). Without a cross-domain reference, it is difficult for stock controllers and auditors to trace *why* a movement occurred.

## Decision
We will add a pair of "Reference" fields to the `InventoryMovement` header model to provide a flexible traceability link.

### 1. Model Structure
- `reference_type`: A choice field defining the source domain.
  - `NONE`: No reference (direct adjustment).
  - `PRODUCTION`: Link to a Production Order.
  - `STOCK_ARRIVAL`: Link to a Stock Arrival Schedule.
  - `OTHER`: Manual reference for edge cases.
- `reference_no`: A `CharField` (max 100) to store the document number/ID of the source record.

### 2. Design Choices
- **Alphanumeric ID**: We chose `CharField` for `reference_no` over `IntegerField` to support diverse numbering systems from external modules or third-party integrations.
- **Nullability**: These fields are optional (`blank=True`, `null=True`) to allow for standard manual inventory corrections.

### 3. Consistency
- The fields will be integrated into the existing **Emerald Green glassmorphism** forms and detail views for a seamless experience.

## Consequences
- **Positive**: Enables advanced reporting (e.g., "Show all stock received against Schedule XYZ").
- **Positive**: Simplifies auditing by providing direct links between financial/production events and warehouse actions.
- **Negative**: Adds two additional columns to the `InventoryMovement` table.
- **Negative**: Increases validation complexity if we eventually enforce existence checks for referenced documents.

## Alternatives Considered
- **Generic ForeignKey (Content_Type)**: Use Django's ContentType system for dynamic relations.
  - *Rejected*: Overly complex for current requirements; simple string references are easier to manage and debug in early stages.
- **Multiple ForeignKeys**: Add optional `ForeignKey` for every possible domain (e.g., `production_order`, `stock_arrival`).
  - *Rejected*: Leads to a "sparse table" with many null columns as more modules are added.
