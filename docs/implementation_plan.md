# Django App Architecture Plan

Based on the ERD we have and your previous successful `stockflow` project, here is how we can split the database tables into functional Django apps.

## Proposed Django Apps

### 1. `catalog` (Reference Data)
The catalog contains all the core master data that other parts of the system will reference.
*   **PRODUCTS:** The items you actually sell/store.
*   **SUPPLIERS:** Who provides the products.
*   **CUSTOMERS:** Who buys the products.

### 2. `inventory` (Stock & Movement)
This app handles where things are and the movement of stock.
*   **WAREHOUSES:** The physical locations.
*   **INBOUND_SHIPMENTS:** Receiving stock from suppliers.
*   **STOCK_DISCREPANCIES:** Any mismatches during receiving.

### 3. `orders` (Reservations & Purchasing)
This process manages the core goal of the preorder system.
*   **RESERVATIONS:** The actual preorder documents.
*   **RESERVATION_ITEMS:** The lines on the preorder.
*   **INVOICES:** Billing documents for the reservations.
*   **EXTERNAL_SYNC_LOGS:** Syncing with the Express system.

### 4. `accounts` or `users` (Authentication)
*   **USERS:** Managing staff, admins, and roles.

## User Review Required

Does this app structure look correct to you? 

> [!NOTE] 
> If you approve, the first step will be to **create the `catalog` app** and implement its specific ERD models (`Product`, `Supplier`, `Customer`), separating them into a `models/` directory exactly like your old project.
