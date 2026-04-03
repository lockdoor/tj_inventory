```mermaid
erDiagram
    %% Roles is_supplier, is_customer can add more role in the future eg. is_shipper, is_consignee
    PARTNER {
        int id PK
        string name UK
        string code UK "e.g. VEND001, CUST001"
        boolean is_supplier
        boolean is_customer
        string tax_id
        string address
        string contact_name
        string phone
        string email
        string note
        string status "active,inactive"
    }
```
