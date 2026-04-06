```mermaid
    erDiagram

    WAREHOUSE {
        int id PK
        string name
        string code UK
        string note
        string status "active,inactive"
    }

    %% Outer Domain: Reference only
    ITEM_CATALOG {
        int id PK
        string sku
        string name
    }

    %% Outer Domain: Reference only
    PARTNER {
        int id PK
        string name
        string code
    }

    %% Stock balance per LOT
    STOCK {
        int id PK
        int warehouse_id FK "CASCADE"
        int item_id FK "Outer Domain Reference"
        string lot_number UK "Globally unique batch ID"
        decimal balance "Current available qty for this lot"
        datetime mfg_date "Manufacturing Date"
        datetime exp_date "Expiry Date"
        string note
        string status "active,expired,quarantined"
    }

    %% Transaction history with Lot tracking
    STOCKCARD {
        int id PK
        int warehouse_id FK "CASCADE"
        int item_id FK "Outer Domain Reference"
        string lot_number "Recorded batch ID"
        int movement_item_id FK "Ref back to source movement"
        decimal qty_in
        decimal qty_out
        datetime created_at
        string note
    }

    %% Header Table: The Document
    INVENTORY_MOVEMENT {
        int id PK
        string document_no UK "e.g. MOV-2024-001"
        string type "IN, OUT, ADJUST, TRANSFER"
        datetime date
        int warehouse_id FK
        int partner_id FK "Outer Domain Reference"
        string note
        string status "draft, completed"
    }

    %% NEW: Uploaded Files (PDF/Images)
    INVENTORY_MOVEMENT_ATTACHMENT {
        int id PK
        int movement_id FK "CASCADE"
        file document_file "FileField / ImageField"
        string file_name
        string note
    }

    %% Detail Table: The Items inside the document
    INVENTORY_MOVEMENT_ITEM {
       int id PK
       int movement_id FK "CASCADE"
       int item_id FK "Outer Domain Reference"
       string lot_number "Mandatory for batch control"
       decimal quantity
       decimal unit_cost "optional: cost price"
       datetime mfg_date "Captured during Draft"
       datetime exp_date "Captured during Draft"
       string note
    }

    %% Relationships
    WAREHOUSE ||--o{ STOCK : "stores_per_lot"
    ITEM_CATALOG ||--o{ STOCK : "has_lot_balances"
    STOCK ||--o{ STOCKCARD : "audit_history"
    INVENTORY_MOVEMENT ||--o{ INVENTORY_MOVEMENT_ITEM : "contains"
    INVENTORY_MOVEMENT ||--o{ INVENTORY_MOVEMENT_ATTACHMENT : "has_files"
    INVENTORY_MOVEMENT_ITEM ||--o{ STOCKCARD : "generates_transaction"
    PARTNER ||--o{ INVENTORY_MOVEMENT : "involved"
```

Business Logic: Status Transitions (Draft <-> Completed)
Event: DRAFT -> COMPLETED
   1. Validate: Ensure lot_number, mfg_date, exp_date are present. For OUT, ensure STOCK >= quantity.
   2. Ledger (STOCKCARD): Generate STOCKCARD record mapping 1-to-1 with Movement Item.
   3. Balance (STOCK): Update STOCK balance (increase for IN, decrease for OUT).

Event: COMPLETED -> DRAFT (Reversal)
   1. Validate: For IN reversals, ensure STOCK balance won't drop below zero.
   2. Ledger (STOCKCARD): Delete or reverse generated STOCKCARD entries first.
   3. Balance (STOCK): Reverse the balance change second (decrease for reversed IN, increase for reversed OUT).

Logic: [BALANCE] Total item balance = sum of STOCK.balance where item_id matches.