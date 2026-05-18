from django import forms
from catalog.models import ItemPackaging


class ItemPackagingForm(forms.ModelForm):
    """
    Form for creating and updating Item Packaging units.
    Styled for the Emerald Green glassmorphism theme.
    """

    class Meta:
        model = ItemPackaging
        fields = ['name', 'quantity', 'barcode', 'note', 'status']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Carton, Box, Dozen, Pallet',
                'class': 'form-input'
            }),
            'quantity': forms.NumberInput(attrs={
                'placeholder': 'Number of pieces (e.g. 24)',
                'min': '1',
                'class': 'form-input'
            }),
            'barcode': forms.TextInput(attrs={
                'placeholder': 'Optional packaging barcode',
                'class': 'form-input'
            }),
            'note': forms.Textarea(attrs={
                'placeholder': 'Optional internal notes...',
                'rows': 2,
                'class': 'form-textarea'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }
