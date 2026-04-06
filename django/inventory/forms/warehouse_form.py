from django import forms
from inventory.models import Warehouse

class WarehouseForm(forms.ModelForm):
    """
    Form for creating and updating Warehouse records.
    """
    class Meta:
        model = Warehouse
        fields = ['name', 'code', 'status', 'note']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'e.g. Central Hub'
            }),
            'code': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'e.g. WH-CN'
            }),
            'status': forms.Select(attrs={
                'class': 'glass-input'
            }),
            'note': forms.Textarea(attrs={
                'class': 'glass-input',
                'rows': 4,
                'placeholder': 'Optional internal notes...'
            }),
        }

    def clean_code(self):
        """Normalize code to uppercase."""
        return self.cleaned_data['code'].strip().upper()
