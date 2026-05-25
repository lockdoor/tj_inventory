# ADR 0012: Shortage Expected Date and Secure Update Architecture

## Status
Accepted

## Context
When material shortages are manually recorded, procurement planners must specify a target "Expected Date" indicating when the items are required. Furthermore, to maintain data accuracy and resolve entry errors, stock controllers need the capability to edit pending shortages (e.g., updating quantities, expected dates, reference documents, and notes).

However, to guarantee audit trail validity and prevent database inconsistencies, resolved shortages—specifically those already cancelled or linked to active Purchase Orders (`po_created`)—must be strictly protected from modifications.

## Decision
We implemented the shortage expected date field and the shortage edit capabilities utilizing a multi-layered security and dynamic form architecture:

### 1. Model Extension and Migrations
- Added `expected_date = models.DateField(null=True, blank=True)` to the `Shortage` model (and historical equivalents) to optionally track demand timelines.
- Integrated the field into shortage stats, records details grid, list table columns, and form templates.

### 2. Service-Layer State Gating (Primary Protection)
In alignment with repository architecture, all business mutation logic is handled within the service boundary class `ShortageService`. To prevent illegitimate modifications at the transaction level, we implemented the state restriction inside `ShortageService.update(...)`:
```python
@staticmethod
def update(shortage, *, user, item=None, request_qty=None, expected_date=None, reference_type=None, reference_id=None, note=None):
    if shortage.status != Shortage.Status.PENDING:
        raise ValidationError("Only pending shortages can be updated.")
    
    if item is not None:
        shortage.item = item
    if request_qty is not None:
        shortage.request_qty = request_qty
    if expected_date is not None:
        shortage.expected_date = expected_date or None
    if reference_type is not None:
        shortage.reference_type = reference_type
    if reference_id is not None:
        shortage.reference_id = reference_id
    if note is not None:
        shortage.note = note

    shortage.updated_by = user
    shortage.full_clean()
    shortage.save()
    return shortage
```

### 3. View-Layer Redirection & Gating
- Implemented `ShortageUpdateView` (subclassing `UpdateView` and gated with the `procurement.view_purchaseorder` permission).
- Overrode `dispatch()` to inspect the target object and instantly redirect to the detail view with a warning banner if the shortage state is not `pending`.
- Overrode `form_valid()` to delegate the update actions to `ShortageService.update(...)` and cleanly catch `ValidationError` instances to return as form-level errors.

### 4. Form Pre-Population and Reusability
The shortage model stores quantities in base units (`request_qty`) without saving the selected package configuration. To seamlessly transition a shortage into the edit view:
- **`ShortageForm.__init__()`**: Scans if an existing instance is bound (`self.instance.pk`) and pre-populates `input_qty` with the stored `request_qty`.
- **Dynamic Template (`shortage_form.html`)**: Frontend page title, header headings, breadcrumb links, and submit actions dynamically morph using a `form.instance.pk` check to seamlessly support both creation ("Record Material Shortage") and editing ("Edit Material Shortage").

### 5. UI Integration
- Added a sleek **Edit Shortage** action button in `shortage_detail.html` next to the "Back to List" button.
- Styled using the premium glassmorphic outline style, visible conditionally only when `shortage.status == 'pending'`.

## Consequences

### Positive:
- **Service Layer Gating**: Enforcing state blocks inside `ShortageService.update()` guarantees that shortages cannot be edited via REST APIs, Django admin, or external shells, ensuring complete transaction safety.
- **DRY Forms and Templates**: Reusing the same `ShortageForm` and `shortage_form.html` for both creation and editing keeps the codebase clean, readable, and easy to maintain.
- **Robust Fallback Mapping**: Correctly handles optional fields like `expected_date` (coercing empty form strings to `None`) and falls back cleanly to base unit quantities during pre-population.

### Negative:
- The editing flow is restricted only to pending shortages, meaning controllers must revert/cancel downstream purchase orders if they wish to unlock and adjust a locked shortage record (a necessary business trade-off for data consistency).
