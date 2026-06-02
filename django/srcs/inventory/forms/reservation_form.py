from django import forms
from django.core.exceptions import ValidationError
from inventory.models import StockReservation, Stock, Warehouse

class StockSelect(forms.Select):
    """
    Custom Select widget that dynamically attaches data-available
    and data-warehouse attributes to option tags for client-side interactions and filtering.
    """
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                stock_id = int(str(value))
                if hasattr(self, 'stock_data_map') and stock_id in self.stock_data_map:
                    stock_info = self.stock_data_map[stock_id]
                    option['attrs']['data-available'] = f"{stock_info['available']:.2f}"
                    option['attrs']['data-warehouse'] = stock_info['warehouse_name']
            except (ValueError, TypeError):
                pass
        return option

class StockModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f"Lot: {obj.lot_number} | SKU: {obj.item.sku} | {obj.item.name} | {obj.warehouse.name} (Avail: {obj.available_qty:.2f})"

class StockReservationForm(forms.ModelForm):
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(status='active').order_by('name'),
        required=False,
        to_field_name='name',
        widget=forms.Select(attrs={'class': 'glass-input'}),
        empty_label="-- All Locations --",
        help_text="Filter the available stock lots by location"
    )
    stock = StockModelChoiceField(
        queryset=Stock.objects.none(),
        widget=StockSelect(attrs={'class': 'glass-input'}),
        help_text="Select an active physical lot with available balance"
    )

    class Meta:
        model = StockReservation
        fields = ['stock', 'quantity', 'reference_type', 'reference_no', 'note']
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'glass-input',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'reference_type': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'reference_no': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'e.g. SO-2026-001'
            }),
            'note': forms.Textarea(attrs={
                'class': 'glass-input',
                'rows': 3,
                'placeholder': 'Explain the reason for this hold/reservation...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit stock choices to active stocks with positive balance.
        # Select_related helps optimize fetching the SKU, name, and warehouse name.
        stocks_qs = Stock.objects.filter(
            status='active',
            balance__gt=0
        ).select_related('item', 'warehouse').order_by('lot_number')
        self.fields['stock'].queryset = stocks_qs

        # Build stock to metadata map
        stock_data_map = {}
        for stock in stocks_qs:
            stock_data_map[stock.id] = {
                'available': stock.available_qty,
                'warehouse_name': stock.warehouse.name
            }
        
        # Pass the map to the select widget
        self.fields['stock'].widget.stock_data_map = stock_data_map

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        stock = cleaned_data.get('stock')
        quantity = cleaned_data.get('quantity')

        if stock and quantity:
            available = stock.available_qty
            if quantity > available:
                self.add_error(
                    'quantity',
                    f"Insufficient available quantity on this lot. "
                    f"Requested: {quantity}, Available: {available}"
                )

        return cleaned_data
