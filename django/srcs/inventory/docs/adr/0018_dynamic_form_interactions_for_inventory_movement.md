# Dynamic Form Interactions for Inventory Movement

The goal of this plan is to enhance the `movement_create.html` and `movement_update.html` interfaces to be highly dynamic, providing contextual filtering based on the selected warehouse and item, and automating lot generation for inbound movements.

## Open Questions

> [!WARNING]
> Please confirm the exact format for the auto-generated lot number:
> 1. Should we use the `express_sku` (e.g., `00-1111-11`) or the internal `system_sku` (e.g., `tg_00-1111-11`) in the `LOT-<sku>-<date>` format?
> 2. What date format do you prefer for the auto-generated lot? (e.g., `YYYYMMDD` like `20260506`, or `DD-MM-YYYY` like `06-05-2026`)?

## Proposed Changes

### Backend API for Lots

#### [NEW] `django/srcs/inventory/views/api_views.py`
- Create a new API view `AvailableLotsAPIView`.
- This view will accept `warehouse_id` and `item_id` as query parameters.
- It will query the `Stock` model and return a JSON list of available `lot_number`s and their current balances for the specified item at the specified warehouse.

#### [MODIFY] `django/srcs/inventory/urls.py`
- Add a new route `path('api/lots/', api_views.AvailableLotsAPIView.as_view(), name='api-lots')` to expose the JSON endpoint.
- Export `AvailableLotsAPIView` in `inventory/views/__init__.py`.

### Backend Form Validation & Automation

#### [MODIFY] `django/srcs/inventory/forms/movement_form.py`
- In `MovementItemForm.clean()`, add logic for Inbound movements:
  - If `lot_number` is submitted empty, automatically generate it using the format `LOT-<sku>-<date>`.
  - Ensure `exp_date` can safely remain null (it is already defined as `null=True, blank=True` in the model, so no model changes are required).

### Frontend Dynamic Interactions

#### [MODIFY] `django/srcs/inventory/templates/inventory/movement_create.html` (and Update View)
- **Item Filtering**: 
  - Add JavaScript to listen to the `Warehouse` dropdown `change` event.
  - When the warehouse changes, read its text (e.g., "TG001") to determine the expected prefix (`tg_` or `tj_`).
  - Loop through all `Item` `<option>` elements in the formset and hide the options that do not match the expected prefix.
- **Lot Dropdown (Datalist)**:
  - Modify the Javascript to dynamically append an HTML `<datalist>` element to the document and link it to the `lot_number` input field (`list="lot-suggestions"`).
  - Add a `change` event listener on the `Item` dropdown. When an item is selected, fetch the available lots from the new API endpoint (`/inventory/api/lots/`).
  - Populate the `<datalist>` with the returned lots. Because it's a datalist, the user can click to select an existing lot (great for Outbound) or freely type a new lot (great for Inbound).

## Verification Plan

### Automated Tests
- Add a unit test to verify the `AvailableLotsAPIView` returns the correct JSON format.
- Add a unit test to `test_movement_views.py` asserting that an inbound form submission without a lot number successfully auto-generates the `LOT-<sku>-<date>` format.

### Manual Verification
- Go to "Create Movement".
- Select Warehouse "TG001" and verify that only `tg_` prefixed items are selectable.
- Select an Item and verify that clicking the Lot input displays a dropdown of existing lots.
- Submit an Inbound movement with an empty lot field and verify it generates the correct lot string without errors.
