# Sales Module ERD (Triple-Ledger Architecture)

This document defines the highly-decoupled relationship between Sales, Inventory, and Procurement for tracking reservations.

```mermaid
erDiagram
    PARTNER ||--o{ SALES_ORDER : "places"
    SALES_ORDER ||--|{ SALES_ORDER_ITEM : "contains"
    CATALOG_ITEM ||--o{ SALES_ORDER_ITEM : "ordered as"
    
    %% The Strategy Bridge (Sales)
    SALES_ORDER_ITEM ||--o{ SALES_ALLOCATION : "fulfillment strategy"
    
    %% The Physical Lock (Inventory)
    SALES_ALLOCATION }o--o| INVENTORY_RESERVATION : "linked to physical hold"
    INVENTORY_RESERVATION }o--o| INVENTORY_STOCK : "locks specific lot"
    
    %% The Future Lock (Procurement)
    SALES_ALLOCATION }o--o| PROCUREMENT_ARRIVAL_RESERVATION : "linked to future hold"
    PROCUREMENT_ARRIVAL_RESERVATION }o--o| PROCUREMENT_ARRIVAL_ITEM : "locks incoming shipment"

    %% The Gap (Shortage)
    SALES_ALLOCATION }o--o| SHORTAGE : "linked to gap"
    SHORTAGE }o--o| PROCUREMENT_ARRIVAL_ITEM : "fill from incoming shipment"
    
    %% Fulfillment Link
    SALES_ORDER ||--o{ INVENTORY_MOVEMENT : "fulfilled by (Outbound)"

    SALES_ORDER {
        string document_no PK "SO-XXXX"
        string partner_id FK "Customer"
        enum status "DRAFT, PREORDER, CONFIRMED, PROCESSING, SHIPPED, CANCELLED"
        date order_date
    }

    SALES_ORDER_ITEM {
        string order_item_id PK
        string item_id FK
        decimal requested_qty "What customer wants"
        decimal allocated_qty "Physical + Future + Shortage"
        decimal fulfilled_qty "What actually left warehouse"
        string status "PENDING, PARTIAL, ALLOCATED, SHIPPED"
    }

    SALES_ALLOCATION {
        string order_item_id FK
        enum source_type "STOCK, ARRIVAL, SHORTAGE"
        string physical_reservation_id FK "Link to Inventory Hold"
        string arrival_reservation_id FK "Link to Procurement Hold"
        string shortage_id FK "Link to Gap/Shortage"
        decimal quantity
    }

    INVENTORY_RESERVATION {
        string stock_id FK "Lot Link"
        string reference_no "SO-101"
        decimal quantity
    }

    PROCUREMENT_ARRIVAL_RESERVATION {
        string arrival_item_id FK "Shipment Link"
        string reference_no "SO-101"
        decimal quantity
    }

    SHORTAGE {
        string shortage_id PK "Unique ID"
        string item_id FK "Item Link"
        string reference_no "SO-101 (Origin)"
        decimal quantity
        string status "PENDING, PO_CREATED, FULFILLED"
    }
```

## Team Responsibilities

1. **Warehouse Admin (Inventory)**:
   - Only sees `INVENTORY_RESERVATION`.
   - Knows exactly what is locked on their shelves.
2. **Stock Controller (Procurement)**:
   - Only sees `PROCUREMENT_ARRIVAL_RESERVATION`.
   - Knows exactly how much of an incoming truck is already sold.
3. **Sales Representative (Sales)**:
   - Sees `SALES_ALLOCATION`.
   - Knows the whole picture for the customer.
