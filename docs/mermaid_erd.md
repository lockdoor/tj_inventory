# Inventory Preorder System ERD

Here is the complete Entity-Relationship Diagram for your **Inventory Preorder System**, rendered natively using Mermaid.js. 

You can view it right here in the chat, or copy the raw markdown block below into any supported platform (GitHub, Notion, Obsidian, Cursor, etc.).

```mermaid
erDiagram

    USERS {
        int id PK
        string username "unique"
        string password
        string name
        string surname
    }

    WAREHOUSES {
        int id PK
        string name
        string address
        string code
    }

    PRODUCTS {
        int id PK
        string sku
        string express_sku
        string name
        string unit
        int warehouse_id FK
        int total_physical_stock
        int total_reserved_stock
    }

    SUPPLIERS {
        int id PK
        string name
        string code
        string address
    }
        
    CUSTOMERS {
        int id PK
        string name
        string code
        string address
    }

    INBOUND_SHIPMENTS {
        int id PK
        int product_id FK
        int quantity
        date expected_arrival_date
        string supplier_id
        string lot_number
        date manufacturing_date
        date expiry_date
        string status "Scheduled, Received, Verified"
    }

    STOCK_DISCREPANCIES {
        int id PK
        int inbound_shipment_id FK
        int actual_quantity
        string resolution_status
        datetime alerted_at
    }

    RESERVATIONS {
        int id PK
        int sales_rep_id FK
        date required_date
        string status "Draft PO, Added To Cart, Reserved, Fulfilled, Shipped"
        datetime created_at
    }

    RESERVATION_ITEMS {
        int id PK
        int reservation_id FK
        int product_id FK
        int quantity
    }

    INVOICES {
        int id PK
        int reservation_id FK
        int generated_by_admin_id FK
        datetime generated_at
    }

    EXTERNAL_SYNC_LOGS {
        int id PK
        int reservation_id FK
        string express_system_ref
        string status "Pending, Synced, Failed"
        datetime sync_attempted_at
    }

    %% Relationships
    PRODUCTS ||--o{ INBOUND_SHIPMENTS : "receives"
    INBOUND_SHIPMENTS ||--o| STOCK_DISCREPANCIES : "may have"
    USERS ||--o{ RESERVATIONS : "drafts/manages"
    USERS ||--o{ INVOICES : "generates"
    RESERVATIONS ||--|{ RESERVATION_ITEMS : "contains"
    PRODUCTS ||--o{ RESERVATION_ITEMS : "reserved as"
    RESERVATIONS ||--o| INVOICES : "billed via"
    RESERVATIONS ||--o| EXTERNAL_SYNC_LOGS : "synced to Express System"
```

> [!NOTE]  
> **Global Audit Fields**  
> To keep the diagram clean and readable, the following fields are omitted from the boxes above, but are assumed to exist on **every** table (or all major tables) as standard mixins:
> * `string note`
> * `string status` (Active/Inactive)
> * `datetime created_at`
> * `int created_by FK`
> * `datetime updated_at`
> * `int updated_by FK`
> * `datetime deleted_at` *(nullable)*
> * `int deleted_by FK` *(nullable)*

## Table Reference

* **`INBOUND_SHIPMENTS`**: Tracks scheduling to verification.
* **`STOCK_DISCREPANCIES`**: Captures differences between Expected and Actual Receiving quantities.
* **`RESERVATIONS`**: Manages the core PO / fulfillment lifecycle.
* **`RESERVATION_ITEMS`**: Specific product lines allocated to a reservation.
* **`EXTERNAL_SYNC_LOGS`**: Centralizes logging for integration with the external "Express" system.
