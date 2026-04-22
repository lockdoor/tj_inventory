from django import forms
from django.forms import inlineformset_factory
from inventory.models import InventoryMovement, InventoryMovementItem, Stock
from catalog.models import Item

class MovementCreateForm(forms.ModelForm):
    """
    Form for the Inventory Movement header. 
    Status is defaulted to Draft via model, excluded from form.
    """
    class Meta:
        model = InventoryMovement
        fields = ['document_no', 'type', 'date', 'warehouse', 'partner', 'recipient', 'note', 'reference_type', 'reference_no']
        widgets = {
            'document_no': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'e.g. DOC-IN-20260001'
            }),
            'type': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'date': forms.DateInput(attrs={
                'class': 'glass-input',
                'type': 'date'
            }),
            'warehouse': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'partner': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'recipient': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'Name of recipient...'
            }),
            'note': forms.Textarea(attrs={
                'class': 'glass-input',
                'rows': 3,
                'placeholder': 'Optional internal notes...'
            }),
            'reference_type': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'reference_no': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'e.g. PROD-2026001'
            }),
        }

class MovementItemForm(forms.ModelForm):
    """
    Individual line item form for the movement document.
    """
    class Meta:
        model = InventoryMovementItem
        fields = ['item', 'lot_number', 'quantity', 'unit_cost', 'mfg_date', 'exp_date', 'note']
        widgets = {
            'item': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'lot_number': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'Batch/Lot'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'glass-input',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'unit_cost': forms.NumberInput(attrs={
                'class': 'glass-input',
                'placeholder': '0.00'
            }),
            'mfg_date': forms.DateInput(attrs={
                'class': 'glass-input',
                'type': 'date'
            }),
            'exp_date': forms.DateInput(attrs={
                'class': 'glass-input',
                'type': 'date'
            }),
            'note': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'Line note...'
            }),
        }

    def __init__(self, *args, **kwargs):
        # Allow passing header-level info for validation before saving
        self.movement_type = kwargs.pop('movement_type', None)
        self.warehouse = kwargs.pop('warehouse', None)
        super().__init__(*args, **kwargs)

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return qty

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        lot_number = cleaned_data.get('lot_number')
        
        # Determine movement context (from init or from existing instance)
        m_type = self.movement_type
        warehouse = self.warehouse
        
        if not m_type or not warehouse:
            # Fallback to instance if available (useful for updates)
            movement = getattr(self.instance, 'movement', None)
            if movement:
                m_type = movement.type
                warehouse = movement.warehouse
        
        if m_type == InventoryMovement.MovementType.OUTBOUND and item and lot_number:
            # Strictly verify Lot existence for Outbound
            exists = Stock.objects.filter(
                warehouse=warehouse,
                item=item,
                lot_number=lot_number.strip().upper()
            ).exists()
            
            if not exists:
                wh_name = getattr(warehouse, 'name', 'the selected warehouse')
                self.add_error('lot_number', f"Lot '{lot_number}' not found in {wh_name}.")
                
        return cleaned_data

# Formset for adding multiple items during creation
MovementItemFormSet = inlineformset_factory(
    InventoryMovement,
    InventoryMovementItem,
    form=MovementItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)
