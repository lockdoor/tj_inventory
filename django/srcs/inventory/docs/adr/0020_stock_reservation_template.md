# ADR 0020: Stock Reservation Template Dynamic Filtering Strategy

## Status
Accepted

## Context
In the Stock Reservation creation interface, users must first filter available physical stock lots by their location (Warehouse) before allocating a lock.
To support a high-quality, reactive user experience, this filtering is performed dynamically on the client-side via JavaScript without requiring full page reloads.

Initially:
1. The `warehouse` dropdown options used the default database `id` as the option `value` attribute.
2. The display text for the `warehouse` options was derived from the model's `__str__` method: `"[code] - [name]"` (e.g., `"TJGLOBAL - TJ GLOBAL"`).
3. The `stock` dropdown labels formatted the location part using only the warehouse name (`obj.warehouse.name`).
4. This misalignment made direct string matching in JavaScript fragile and complex because the selected option's value did not correspond to the location segment in the stock lot's option text.

## Decision
To make dynamic filtering extremely robust and maintainable, we implemented the following frontend-backend synergy:

### 1. Form Option Values Mapped to Warehouse Name
We configured the helper `warehouse` field in `StockReservationForm` using `to_field_name='name'`:
```python
warehouse = forms.ModelChoiceField(
    queryset=Warehouse.objects.filter(status='active').order_by('name'),
    required=False,
    to_field_name='name',
    widget=forms.Select(attrs={'class': 'glass-input'}),
    empty_label="-- All Locations --",
    help_text="Filter the available stock lots by location"
)
```
This forces the HTML output to render `<option value="Warehouse Name">` (e.g., `<option value="TJ GLOBAL">TJGLOBAL - TJ GLOBAL</option>`), matching the value attribute exactly to the name representation.

### 2. Standardized Stock Lot Option Text & Precision
The `StockModelChoiceField` is formatted with exact fields and double-decimal float representation:
```python
class StockModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"Lot: {obj.lot_number} | SKU: {obj.item.sku} | {obj.item.name} | {obj.warehouse.name} (Avail: {obj.available_qty:.2f})"
```

### 3. Client-Side Value Matching
In the template `reservation_form.html`, the JavaScript dynamic filtering checks the select value (`selectedValue`) against the parsed warehouse name from the stock option label:
```javascript
const selectedValue = warehouseSelect.value; // e.g. "TJ GLOBAL"
// ...
const parts = opt.text.split(' | ');
if (parts.length >= 4) {
    const warehousePart = parts[3]; // e.g. "TJ GLOBAL (Avail: 3084.00)"
    const lastOpenParenIndex = warehousePart.lastIndexOf(' (Avail:');
    if (lastOpenParenIndex !== -1) {
        const warehouseName = warehousePart.substring(0, lastOpenParenIndex).trim();
        if (warehouseName === selectedValue) {
            stockSelect.appendChild(opt.cloneNode(true));
        }
    }
}
```

## Consequences
- **Positive**: Direct matching on the select `value` attribute makes JavaScript logic much simpler and less error-prone.
- **Positive**: Decouples the dropdown display text from the matching logic. Modifying the display representation of the warehouse dropdown (e.g., adding localized descriptions) will not break the filtering mechanism.
- **Positive**: Guarantees consistent decimal-place presentation (`.2f`) for available quantities in stock choices.
- **Negative**: Assumes warehouse names are unique. While warehouse codes are the primary database unique identifiers, name uniqueness is functionally enforced at the business level, and since `warehouse` is merely a temporary frontend filter field that isn't persisted on reservation creation, any edge cases do not jeopardize database integrity.
