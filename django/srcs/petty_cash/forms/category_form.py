from django import forms
from petty_cash.models import PettyCashCategory


class PettyCashCategoryForm(forms.ModelForm):
    """
    Form for creating and updating PettyCashCategory.
    """
    class Meta:
        model = PettyCashCategory
        fields = ['code', 'name', 'company', 'note']
        widgets = {
            'code': forms.TextInput(attrs={
                'placeholder': 'GL Account Code (e.g. 5101-01)',
                'class': 'form-input'
            }),
            'name': forms.TextInput(attrs={
                'placeholder': 'Category Name (e.g. Travel Expenses)',
                'class': 'form-input'
            }),
            'company': forms.Select(attrs={
                'class': 'form-select'
            }),
            'note': forms.Textarea(attrs={
                'placeholder': 'Optional category notes...',
                'class': 'form-input',
                'rows': 3
            }),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code', '')
        return code.strip().upper()
