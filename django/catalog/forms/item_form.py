from django import forms
from catalog.models import Item, Category

class ItemForm(forms.ModelForm):
    """
    Form for creating and updating Items.
    Styled for the Emerald Green glassmorphism theme.
    """
    class Meta:
        model = Item
        fields = ['category', 'sku', 'express_sku', 'name', 'unit', 'note', 'status']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'sku': forms.TextInput(attrs={
                'placeholder': 'Unique internal SKU',
                'class': 'form-input uppercase'
            }),
            'express_sku': forms.TextInput(attrs={
                'placeholder': 'Optional Express system SKU',
                'class': 'form-input uppercase'
            }),
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. iPhone 15 Pro Max',
                'class': 'form-input'
            }),
            'unit': forms.TextInput(attrs={
                'placeholder': 'e.g. Pcs, Box, Set',
                'class': 'form-input'
            }),
            'note': forms.Textarea(attrs={
                'placeholder': 'Optional internal notes...',
                'rows': 3,
                'class': 'form-textarea'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter category to only active categories
        self.fields['category'].queryset = Category.objects.filter(
            is_deleted=False,
            status=Category.Status.ACTIVE
        )
        self.fields['category'].empty_label = "Unassigned"
