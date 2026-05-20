from django import forms
from django.forms import inlineformset_factory
from ..models.arrival import Arrival, ArrivalItem
from ..models.purchase_order import PurchaseOrder

class ArrivalForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter POs to only show submitted ones
        self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(
            status=PurchaseOrder.Status.SUBMITTED
        ).order_by('-created_at')
        self.fields['purchase_order'].required = False

    class Meta:
        model = Arrival
        fields = ['document_no', 'purchase_order', 'partner', 'warehouse', 'expected_date', 'note']
        widgets = {
            'document_no': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. ARR-2024-001'}),
            'purchase_order': forms.Select(attrs={'class': 'form-control'}),
            'partner': forms.Select(attrs={'class': 'form-control'}),
            'warehouse': forms.Select(attrs={'class': 'form-control'}),
            'expected_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

from catalog.models import ItemPackaging

class ArrivalItemForm(forms.ModelForm):
    class Meta:
        model = ArrivalItem
        fields = ['item', 'po_item', 'packaging', 'expected_qty', 'received_qty', 'mfg_date', 'exp_date']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control item-select'}),
            'po_item': forms.HiddenInput(),
            'packaging': forms.Select(attrs={'class': 'form-control packaging-select'}),
            'expected_qty': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'received_qty': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'readonly': 'readonly'}),
            'mfg_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'exp_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['packaging'].queryset = ItemPackaging.objects.filter(is_deleted=False)


ArrivalItemFormSet = inlineformset_factory(
    Arrival,
    ArrivalItem,
    form=ArrivalItemForm,
    extra=1,
    can_delete=True
)
