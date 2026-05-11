from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils import timezone
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.initial['type'] = InventoryMovement.MovementType.OUTBOUND
            self.initial['date'] = timezone.now().date()
            self.initial['warehouse'] = 1

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
        # Lot number can be auto-generated for inbound, so it's not strictly required by the form
        self.fields['lot_number'].required = False
        
        # If this is an existing item line (Update view), lock down the core item/lot fields
        if self.instance and self.instance.pk:
            locked_fields = ['item', 'lot_number', 'mfg_date', 'exp_date', 'unit_cost']
            for field in locked_fields:
                self.fields[field].disabled = True
                self.fields[field].widget.attrs['class'] += ' disabled-field'
                self.fields[field].widget.attrs['style'] = 'opacity: 0.6; pointer-events: none; background: rgba(255,255,255,0.05);'

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
        
        if m_type == InventoryMovement.MovementType.INBOUND and not lot_number and item:
            exp_date = cleaned_data.get('exp_date')
            if exp_date:
                date_str = exp_date.strftime('%Y%m%d')
            else:
                from django.utils import timezone
                date_str = timezone.now().strftime('%Y%m%d')
            lot_number = f"LOT-{item.sku}-{date_str}"
            cleaned_data['lot_number'] = lot_number

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
                
        if m_type == InventoryMovement.MovementType.OUTBOUND and not lot_number:
            self.add_error('lot_number', "Lot number is required for outbound movements.")

        return cleaned_data

from django.forms.models import BaseInlineFormSet

class BaseMovementItemFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        seen_items_lots = set()
        for form in self.forms:
            if self.can_delete and self._should_delete_form(form):
                continue
                
            item = form.cleaned_data.get('item')
            lot_number = form.cleaned_data.get('lot_number')
            
            if item:
                # lot_number might be None/empty string
                lot_number = lot_number.strip().upper() if lot_number else ''
                key = (item.pk, lot_number)
                
                if key in seen_items_lots:
                    raise ValidationError("Item and lot number already exists in movement.")
                seen_items_lots.add(key)

# Formset for adding multiple items during creation
MovementItemFormSet = inlineformset_factory(
    InventoryMovement,
    InventoryMovementItem,
    form=MovementItemForm,
    formset=BaseMovementItemFormSet,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)
