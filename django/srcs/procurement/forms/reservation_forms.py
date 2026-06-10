from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from procurement.models import ArrivalReservation, ArrivalItem, Arrival
from inventory.models import Warehouse

class ArrivalItemModelChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        expected_str = f"{obj.expected_qty:.2f} {obj.packaging.name}" if obj.packaging else f"{obj.expected_qty:.2f} pcs"
        if obj.packaging:
            expected_str += f" ({obj.expected_pieces:.2f} pcs)"
        return f"Arrival: {obj.arrival.document_no} | SKU: {obj.item.sku} | {obj.item.name} | Whse: {obj.arrival.warehouse.name} (Expected: {expected_str}, Avail: {obj.available_qty:.2f} pcs)"

class ArrivalReservationForm(forms.ModelForm):
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(status='active').order_by('name'),
        required=False,
        to_field_name='name',
        widget=forms.Select(attrs={'class': 'glass-input'}),
        empty_label="-- All Locations --",
        help_text="Filter dynamic arrival lines by destination warehouse"
    )
    arrival_item = ArrivalItemModelChoiceField(
        queryset=ArrivalItem.objects.none(),
        widget=forms.Select(attrs={'class': 'glass-input'}),
        help_text="Select an active expected arrival line with remaining quantity"
    )

    class Meta:
        model = ArrivalReservation
        fields = ['arrival_item', 'quantity', 'reference_type', 'reference_no', 'note']
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
                'placeholder': 'Explain the reason for this pre-allocation...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit arrival items to scheduled/receiving arrivals that are not soft-deleted
        self.fields['arrival_item'].queryset = ArrivalItem.objects.filter(
            arrival__status__in=[Arrival.Status.SCHEDULED, Arrival.Status.RECEIVING],
            arrival__is_deleted=False
        ).select_related('item', 'arrival__partner', 'arrival__warehouse').order_by('arrival__expected_date', 'arrival__document_no')

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity is not None and quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        arrival_item = cleaned_data.get('arrival_item')
        quantity = cleaned_data.get('quantity')

        if arrival_item and quantity:
            # Query reservations on this arrival_item to calculate actual remaining available qty
            reserved_qs = ArrivalReservation.objects.filter(
                arrival_item=arrival_item,
                is_deleted=False,
                status=ArrivalReservation.ReservationStatus.RESERVED
            )
            if self.instance and self.instance.pk:
                reserved_qs = reserved_qs.exclude(pk=self.instance.pk)
            
            total_reserved = reserved_qs.aggregate(total=models.Sum('quantity'))['total'] or 0
            available = arrival_item.expected_pieces - total_reserved

            if quantity > available:
                self.add_error(
                    'quantity',
                    f"Insufficient available expected quantity on this arrival line. "
                    f"Requested: {quantity}, Available: {available:.2f}"
                )

        return cleaned_data
