from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from procurement.models import Shortage
from catalog.models import Item, ItemPackaging
from inventory.models import Warehouse


class ShortageItemSelect(forms.Select):
    """
    Custom Select widget that dynamically attaches data-warehouse attributes
    to option tags for dynamic client-side filtering matching ADR 0010.
    """
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        if value:
            try:
                item_id = int(str(value))
                if hasattr(self, 'item_warehouses_map') and item_id in self.item_warehouses_map:
                    # Map the warehouse names/codes as comma-separated values
                    option['attrs']['data-warehouse'] = ",".join(self.item_warehouses_map[item_id])
            except (ValueError, TypeError):
                pass
        return option


class ShortageItemModelChoiceField(forms.ModelChoiceField):
    """
    Subclasses ModelChoiceField to return clean display labels.
    """
    def label_from_instance(self, obj):
        return f"SKU: {obj.sku} | {obj.name}"


class ShortageForm(forms.ModelForm):
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(status='active').order_by('name'),
        required=False,
        to_field_name='code',
        widget=forms.Select(attrs={'class': 'glass-input'}),
        empty_label="-- All Locations --",
        help_text="Optional. Filter items by warehouse association."
    )
    item = ShortageItemModelChoiceField(
        queryset=Item.objects.none(),
        widget=ShortageItemSelect(attrs={'class': 'glass-input'}),
        help_text="Select the active catalog item experiencing a shortage"
    )
    packaging = forms.ModelChoiceField(
        queryset=ItemPackaging.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'glass-input'}),
        help_text="Optional. Select packaging type to calculate base units."
    )
    input_qty = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'glass-input',
            'placeholder': '0.00',
            'step': '0.01'
        }),
        help_text="Enter quantity in selected packaging units."
    )

    class Meta:
        model = Shortage
        fields = ['item', 'request_qty', 'reference_type', 'reference_id', 'note']
        widgets = {
            'request_qty': forms.HiddenInput(),
            'reference_type': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'reference_id': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'e.g. SO-2026-001'
            }),
            'note': forms.Textarea(attrs={
                'class': 'glass-input',
                'rows': 3,
                'placeholder': 'Specify any context about this shortage...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['request_qty'].required = False
        
        # Optimize queryset with prefetch_related for Stocks to prevent N+1 DB queries
        items_qs = Item.objects.filter(
            status='active'
        ).prefetch_related('stocks__warehouse').order_by('sku')
        self.fields['item'].queryset = items_qs
        
        # Build item to warehouse codes map (deduplicated)
        item_warehouses_map = {}
        for item in items_qs:
            item_warehouses_map[item.id] = list(set(stock.warehouse.code for stock in item.stocks.all()))
        
        # Pass the map to the select widget
        self.fields['item'].widget.item_warehouses_map = item_warehouses_map
        
        self.fields['packaging'].queryset = ItemPackaging.objects.filter(
            status='active'
        ).select_related('item')
        self.fields['packaging'].label_from_instance = lambda obj: f"{obj.name} ({obj.quantity} pcs)"

    def clean(self):
        cleaned_data = super().clean()
        input_qty = cleaned_data.get('input_qty')
        packaging = cleaned_data.get('packaging')

        if input_qty is not None:
            if input_qty <= 0:
                self.add_error('input_qty', "Quantity must be greater than zero.")
            
            # Compute request_qty in base units
            if packaging:
                multiplier = packaging.quantity
                cleaned_data['request_qty'] = input_qty * Decimal(str(multiplier))
            else:
                cleaned_data['request_qty'] = input_qty
                
        return cleaned_data
