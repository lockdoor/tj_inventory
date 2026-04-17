# Implementation Plan: Seed Stock Migration

The goal is to migrate stock data from `stock_migration.json` into the Django inventory system. Since the formal Partner list is not yet ready, we will add a `recipient` string field to handled outbound movements for the time being.

## User Review Required

> [!IMPORTANT]
> - A new field `recipient` (CharField) will be added to the `InventoryMovement` model.
> - The migration will use a default lot number ('MIGRATION-LOT') for all imported stock since the source Excel doesn't specify lots.
> - Movements will be created in `COMPLETED` status using the `MovementService`.

## Proposed Changes

---

### Inventory Model

#### [MODIFY] [movement.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/models/movement.py)
- Add `recipient` CharField to `InventoryMovement` model.
- Default to empty string.

---

### Management Command

#### [NEW] [seed_stock_migration.py](file:///Users/pitsanunamnil/Desktop/work/tj/tj_inventory/django/inventory/management/commands/seed_stock_migration.py)
- Load JSON from `private/data/stock_migration.json`.
- Logic:
    - **Transaction Safety**: Wrap the entire operation in `transaction.atomic()`.
    - **User Attribution**: Attribute actions to the first found executive or system user.
    - **Record Processing**:
        - **Resolve Item**: Match by `sku`. **Raise a ValueError** if the SKU is not found.
        - **Resolve Warehouse**: Use the `warehouse` code provided in each JSON entry. **Raise a ValueError** if not found.
        - **Lot Identification**: Ensure uniqueness by combining SKU and Expiry Date. Format: `LOT-{sku}-{exp_date}`.
        - **Recipient Handling**: 
            - For `outbound`: Map JSON `partner` field to the new `recipient` CharField on the movement.
            - For `inbound`: No person/partner logic applied.
        - **Core Logic**: Use `MovementService` to ensure `StockCard` and inventory balances are correctly calculated.



## Open Questions

- Should I automatically create `Item` objects if the SKU in JSON doesn't exist in the database?
- Is 'WH-MAIN' a suitable default warehouse code?

## Verification Plan

### Automated Tests
- Run `python manage.py makemigrations` and `python manage.py migrate`.
- Run `python manage.py seed_stock_migration`.
- Verify counts in shell: `InventoryMovement.objects.count()`.

### Manual Verification
- Check the Django Admin / Inventory UI to ensure movements appear with the correct `recipient` names.
