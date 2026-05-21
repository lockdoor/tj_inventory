# ADR 0010: Arrival Reservation Template Dynamic Filtering Strategy

## Status
Accepted

## Context
In the Arrival Reservation creation interface, users must allocate a lock on incoming expected stock lines (ArrivalItems) that are currently in transit. 
To deliver a responsive, reactive user experience, users need to filter the available expected lot options dynamically by their destination location (Warehouse) on the client side without triggering a full page refresh.

Like the physical stock reservation system:
1. The destination `warehouse` dropdown options use the database `name` field as the option value.
2. The `arrival_item` dropdown displays rich metadata: the document number, SKU, item name, warehouse destination name, expected quantity, and net remaining available quantity.
3. String-matching dynamic JavaScript in the template performs real-time client-side option filtering.
4. Soft-deleted expected arrivals must be excluded from the queryset.

## Decision
To implement an extremely clean and robust arrival-side dynamic template matching mechanism, we implemented the following strategies:

### 1. Form Option Values Mapped to Warehouse Name
The helper `warehouse` field in `ArrivalReservationForm` uses `to_field_name='name'`:
```python
warehouse = forms.ModelChoiceField(
    queryset=Warehouse.objects.filter(status='active').order_by('name'),
    required=False,
    to_field_name='name',
    widget=forms.Select(attrs={'class': 'glass-input'}),
    empty_label="-- All Locations --",
    help_text="Filter dynamic arrival lines by destination warehouse"
)
```
This maps the HTML `<option>` value attribute directly to the destination warehouse name (e.g., `<option value="Main Warehouse">`).

### 2. Standardized Expected Lot Choices & Exclusions
The subclassed `ArrivalItemModelChoiceField` represents choices with double-decimal precision:
```python
class ArrivalItemModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"Arrival: {obj.arrival.document_no} | SKU: {obj.item.sku} | {obj.item.name} | Whse: {obj.arrival.warehouse.name} (Expected: {obj.expected_qty:.2f}, Avail: {obj.available_qty:.2f})"
```
To ensure that expected stock lines belonging to soft-deleted shipments are completely hidden, we restrict the `arrival_item` queryset:
```python
self.fields['arrival_item'].queryset = ArrivalItem.objects.filter(
    arrival__status__in=[Arrival.Status.SCHEDULED, Arrival.Status.RECEIVING],
    arrival__is_deleted=False
).select_related('item', 'arrival__partner', 'arrival__warehouse').order_by('arrival__expected_date', 'arrival__document_no')
```

### 3. Client-Side Value Matching
Inside `reservation_form.html` in the procurement app, the dynamic filtering matches the select value against the parsed warehouse name in the arrival item display label:
```javascript
const parts = opt.text.split(' | ');
if (parts.length >= 4) {
    const warehousePart = parts[3]; // e.g., "Whse: Main Warehouse (Expected: 100.00..."
    if (warehousePart.startsWith('Whse: ')) {
        const warehouseSegment = warehousePart.substring(6).trim(); // Remove "Whse: " prefix
        const lastOpenParenIndex = warehouseSegment.lastIndexOf(' (Expected:');
        if (lastOpenParenIndex !== -1) {
            const warehouseName = warehouseSegment.substring(0, lastOpenParenIndex).trim();
            if (warehouseName === selectedValue) {
                arrivalItemSelect.appendChild(opt.cloneNode(true));
            }
        }
    }
}
```

## Consequences

### Positive:
- **Consistency**: The user experience and matching architecture mirror the physical stock reservation system, easing maintainability.
- **Robustness**: Using `to_field_name='name'` ensures that modifying option display text will not break JavaScript filtering logic.
- **Data Integrity**: Filtering by `arrival__is_deleted=False` guarantees that no commitments can be allocated against soft-deleted shipments.
- **Visual Clarity**: Displays exact remaining available quantities to planners with standardized `.2f` float representations.

### Negative:
- **Warehouse Name Uniqueness**: Relies on warehouse names being unique at the business level. Since the warehouse selector is a non-persisted frontend filtering convenience, any edge cases do not affect database or relational schema constraints.
