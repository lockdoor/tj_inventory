# ADR 0011: Shortage Context List and Create Form Architecture

## Status
Accepted

## Context
In the procurement workflow, planners and stock controllers must manually record item shortages ("Record Material Shortage") to accumulate stock control requirements before deciding to issue Purchase Orders (POs) to suppliers.

To deliver an exceptional user experience and maintain data integrity, the system requires:
1. A secure, permission-gated shortage creation interface restricted to users with `procurement.view_purchaseorder` permissions.
2. A list dashboard displaying outstanding shortages with visual KPIs (e.g., pending count, total pieces gap, unique short items).
3. A dynamic Warehouse Location filter dropdown on the creation form to isolate products associated with that warehouse.
4. An alternative Item Packaging selection dropdown (e.g., Box, Carton) to let users input quantities in standard packaging units.
5. Dynamic client-side unit conversion calculating base quantities in pieces (pcs) in real-time on the UI.
6. Absolute data validation security by executing unit conversion on the backend Django Form `clean()` boundary.

## Decision
We implemented the Shortage context list view and creation form under the `procurement` app using the following design and architecture decisions:

### 1. Custom Django Form Widget for Dynamic Attributes
In Django, defining custom attributes inside standard `forms.Select` widgets inside `Meta` classes cannot dynamically read instance values at runtime because `Meta` is compiled during class load time.
To bypass this limitation and inject the `data-warehouse` attribute containing only unique warehouse codes (e.g., `TG001` instead of duplicates like `TG001,TG001`), we:
- Inherited from `forms.Select` to create `ShortageItemSelect` and overrode `create_option()`.
- Computed a deduplicated mapping dictionary in `ShortageForm.__init__` using Python `set()` list conversions to extract unique warehouse codes from active product stocks.
- Transferred this map directly to the widget at instantiation time:

```python
class ShortageItemSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                item_id = int(str(value))
                if hasattr(self, 'item_warehouses_map') and item_id in self.item_warehouses_map:
                    # Inject unique comma-separated warehouse codes
                    option['attrs']['data-warehouse'] = ",".join(self.item_warehouses_map[item_id])
            except (ValueError, TypeError):
                pass
        return option
```

### 2. Client-Side Dynamic Warehouse Filtering (ADR 0010 Alignment)
Aligning with the dynamic matching approach defined in ADR 0010, the `warehouse` selector is mapped to the warehouse code using `to_field_name='code'`:
```python
warehouse = forms.ModelChoiceField(
    queryset=Warehouse.objects.filter(status='active').order_by('name'),
    required=False,
    to_field_name='code',
    widget=forms.Select(attrs={'class': 'glass-input'}),
    empty_label="-- All Locations --",
    help_text="Optional. Filter items by warehouse association."
)
```
In the template `shortage_form.html`, dynamic JavaScript monitors changes on `warehouse`. It parses the comma-separated `data-warehouse` codes embedded inside the item select options and shows or hides options matching the active selection.

### 3. Dual-Layer Packaging Conversion
To convert quantities from packaging units (e.g. Box of 12 pcs) to base pieces reliably:
- **UI Layer (Live Calculator)**: Packaging data is injected into the template as a secure JSON payload (`<script id="packagings-data" type="application/json">`). Live Javascript tracks the inputs and displays a glassmorphic conversion widget (`10.00 Box = 120.00 pcs`) instantly.
- **Backend Validation Layer**: A hidden field `request_qty` is populated by the frontend, but is fully sanitized and recalculated on the Django form `clean()` method. This prevents manual client-side tampering:
```python
def clean(self):
    cleaned_data = super().clean()
    input_qty = cleaned_data.get('input_qty')
    packaging = cleaned_data.get('packaging')

    if input_qty is not None:
        if input_qty <= 0:
            self.add_error('input_qty', "Quantity must be greater than zero.")
        
        # Calculate request_qty in base units safely on the backend
        if packaging:
            multiplier = packaging.quantity
            cleaned_data['request_qty'] = input_qty * Decimal(str(multiplier))
        else:
            cleaned_data['request_qty'] = input_qty
            
    return cleaned_data
```

### 4. Database Optimization
To eliminate N+1 database queries during bulk preloads of warehouse associations and packaging options, querysets are optimized inside `ShortageCreateView` and `ShortageForm.__init__` using:
- `prefetch_related('stocks__warehouse')` on `Item` querysets.
- `select_related('item')` on `ItemPackaging` querysets.
- Filtering with `status='active'` and excluding soft-deleted entities (`is_deleted=False`).

## Consequences

### Positive:
- **Data Integrity**: Calculating packaging multiplier conversions on the Django Form boundary ensures that invalid or manipulated values never reach the DB layer.
- **Improved UX**: The live glassmorphic conversion banner provides instant feedback, matching the premium look and feel of the TJ Inventory system.
- **Deduplicated Warehouse Mapping**: Deduplicating the active warehouses into a `set` yields precise single attributes like `data-warehouse="TG001"` instead of long redundant lists.
- **Performance**: Preloading and caching warehouse maps on the select widget prevents performance degradation under high database loads.

### Negative:
- The custom Django Widget requires manual assignment of the helper map inside the form's `__init__` constructor, meaning form reuse requires explicit widget binding.
