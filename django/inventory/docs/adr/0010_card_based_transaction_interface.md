# ADR 0010: Card-Based Transaction Interface

## Status
Accepted

## Context
Transaction documents in inventory systems often require multiple line items. As documents grow in complexity (Lot Number, Cost, Dates, Notes), a standard table becomes horizontally bloated and difficult to manage on smaller screens. 

## Decision
We will transition the **Movement Creation** interface from a traditional table to a **Card-Based "Shopping Cart"** layout.

### 1. Item Visualization (Summary)
- Each transaction item is rendered as a standalone **Glassmorphism Card**.
- **Header**: Item Name, SKU, and Quantity (large, bold).
- **Metadata**: Warehouse and Type indicators.

### 2. Interaction Model (Expandable Details)
- **Click to Detail**: Clicking a card will expand or open a "Detail Panel" containing all input fields (`Lot Number`, `Unit Cost`, `MFG Date`, `EXP Date`, `Note`).
- **Real-Time Summary**: Changing the "Quantity" or "Lot" in the detail panel will immediately update the summary text on the card header.

### 3. Conditional Inbound Logical
- **Lot Attributes**: `MFG Date` and `EXP Date` fields are context-aware. They will only be visible when the parent Movement Type is set to **Inbound**.
- **Lot Management**: Inbound movements allow for "New LOT" entry with full traceability.

## Consequences
- **Positive**: Better mobile responsiveness and space management.
- **Positive**: Reduces cognitive load by hiding non-essential fields (Dates/Notes) until needed.
- **Negative**: Requires more complex JavaScript for managing the expanded state and field visibility toggles.
- **Negative**: More vertical scrolling compared to a dense table.

## Alternatives Considered
- **Dense Table with Tooltips**: Keep the table but hide details in tooltips.
  - *Rejected*: Poor editing experience; tooltips are for viewing, not input.
- **Full Modal per Item**: Click "Edit" to open a modal for item details.
  - *Rejected*: Too disconnected from the "Summary list" view; breaks the flow of document creation.
