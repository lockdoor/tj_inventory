# Procurement ERD: Purchase Orders & Arrivals

This diagram focuses exclusively on the Procurement module's supply-side models.

```mermaid
erDiagram
    %% External References
    PARTNER ||--o{ PURCHASE_ORDER : "supplies"
    PARTNER ||--o{ ARRIVAL : "ships"
    ITEM ||--o{ PURCHASE_ORDER_ITEM : "ordered"
    ITEM ||--o{ ARRIVAL_ITEM : "shipped"
    WAREHOUSE ||--o{ ARRIVAL : "receives"

    %% Internal Procurement Models
    PURCHASE_ORDER ||--|{ PURCHASE_ORDER_ITEM : "contains"
    PURCHASE_ORDER ||--o{ ARRIVAL : "fulfilled by"
    ARRIVAL ||--o{ ARRIVAL_ITEM : "contains"
    PURCHASE_ORDER_ITEM ||--o{ ARRIVAL_ITEM : "tracks fulfillment"

    %% Attachments Support
    PURCHASE_ORDER ||--o{ PURCHASE_ORDER_ATTACHMENT : "has_files"
    ARRIVAL ||--o{ ARRIVAL_ATTACHMENT : "has_files"

    PURCHASE_ORDER {
        string document_no PK
        string partner_code FK "external.Partner"
        date expected_date
        enum status "DRAFT, SUBMITTED, CLOSED, CANCELLED"
        string created_by FK "external.User"
        string note
    }

    PURCHASE_ORDER_ITEM {
        string po_no FK
        string item_sku FK
        decimal order_qty
        decimal unit_cost
    }

    PURCHASE_ORDER_ATTACHMENT {
        int id PK
        int purchase_order_id FK "CASCADE"
        file document_file "FileField"
        string file_name
        string note
    }

    ARRIVAL {
        string document_no PK
        string po_no FK "PurchaseOrder (Optional)"
        string partner_code FK "external.Partner"
        string warehouse_code FK "external.Warehouse"
        date expected_date
        enum status "SCHEDULED, RECEIVED"
    }

    ARRIVAL_ITEM {
        string arrival_no FK
        string item_sku FK
        decimal expected_qty
        decimal received_qty
    }

    ARRIVAL_ATTACHMENT {
        int id PK
        int arrival_id FK "CASCADE"
        file document_file "FileField"
        string file_name
        string note
    }

    SHORTAGE {
        string sku FK "external.Item"
        string created_by FK "external.User"
        string reference_type "SELL_ORDER, PRODUCTION, OTHER"
        int request_qty
        string status "PENDING, PO_CREATED, CANCELLED"
        string po_no FK "PurchaseOrder (Optional)"
    }

```

## Relationship Details

1.  **External References**:
    *   `Partner`: From the `partners` app.
    *   `Item`: From the `catalog` app.
    *   `Warehouse`: From the `inventory` app.
2.  **Purchase Order (PO)**: Represents the contract or intent to buy.
3.  **Arrival**: Represents the actual shipment from the supplier. It can be linked to a `PurchaseOrder` for fulfillment tracking, or be "Standalone" if no PO exists.
4.  **Arrival Item**: Tracks the specific quantities received. If linked to a `PurchaseOrderItem`, it helps calculate "Remaining to Receive" on the PO.
5.  **Attachments**: Both Purchase Orders and Arrivals support multiple file attachments (PDFs, invoice images, packing lists) for audit compliance and record-keeping.
