from django import forms
from catalog.models import Category

class CategoryForm(forms.ModelForm):
    """
    Form for creating and updating Categories.
    Styled for the Emerald Green glassmorphism theme.
    """
    class Meta:
        model = Category
        fields = ['name', 'code', 'parent', 'note', 'status']
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Smartphones',
                'class': 'form-input'
            }),
            'code': forms.TextInput(attrs={
                'placeholder': 'e.g. SMART-01',
                'class': 'form-input uppercase'
            }),
            'parent': forms.Select(attrs={
                'class': 'form-select'
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
        # Filter parent to only active/non-deleted categories
        self.fields['parent'].queryset = Category.objects.filter(
            is_deleted=False, 
            status=Category.Status.ACTIVE
        )
        self.fields['parent'].empty_label = "None (Root Category)"
