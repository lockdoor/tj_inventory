from django import forms
from django.forms import inlineformset_factory
from inventory.models import InventoryMovement, InventoryMovementItem
from catalog.models import Item

class MovementCreateForm(forms.ModelForm):
    """
    Form for the Inventory Movement header. 
    Status is defaulted to Draft via model, excluded from form.
    """
    class Meta:
        model = InventoryMovement
        fields = ['document_no', 'type', 'date', 'warehouse', 'partner', 'note']
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
            'note': forms.Textarea(attrs={
                'class': 'glass-input',
                'rows': 3,
                'placeholder': 'Optional internal notes...'
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

    def clean_quantity(self):
        qty = self.cleaned_data.get('quantity')
        if qty is not None and qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return qty

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
