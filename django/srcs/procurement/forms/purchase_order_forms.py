from django import forms
from django.forms import inlineformset_factory
from ..models import PurchaseOrder, PurchaseOrderItem
from partners.models import Partner
from catalog.models import ItemPackaging

class PurchaseOrderForm(forms.ModelForm):
    """
    Form for the Purchase Order header.
    """
    class Meta:
        model = PurchaseOrder
        fields = ['document_no', 'partner', 'expected_date', 'note']
        widgets = {
            'document_no': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'e.g. PO-2026-0001'
            }),
            'partner': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'expected_date': forms.DateInput(attrs={
                'class': 'glass-input',
                'type': 'date'
            }),
            'note': forms.Textarea(attrs={
                'class': 'glass-input',
                'rows': 3,
                'placeholder': 'Optional internal notes...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter partners to only show active suppliers
        self.fields['partner'].queryset = Partner.objects.filter(
            status=Partner.Status.ACTIVE,
            is_supplier=True,
            is_deleted=False
        )

class PurchaseOrderItemForm(forms.ModelForm):
    """
    Form for individual line items in a Purchase Order.
    """
    class Meta:
        model = PurchaseOrderItem
        fields = ['item', 'packaging', 'order_qty', 'unit_cost']
        widgets = {
            'item': forms.Select(attrs={
                'class': 'glass-input item-select'
            }),
            'packaging': forms.Select(attrs={
                'class': 'glass-input packaging-select'
            }),
            'order_qty': forms.NumberInput(attrs={
                'class': 'glass-input',
                'placeholder': '0.00',
                'step': '0.01'
            }),
            'unit_cost': forms.NumberInput(attrs={
                'class': 'glass-input',
                'placeholder': '0.00',
                'step': '0.01'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['packaging'].queryset = ItemPackaging.objects.filter(is_deleted=False)

    def clean_order_qty(self):

        qty = self.cleaned_data.get('order_qty')
        if qty is not None and qty <= 0:
            raise forms.ValidationError("Quantity must be greater than zero.")
        return qty

# Formset for managing PO items inline
PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True
)
