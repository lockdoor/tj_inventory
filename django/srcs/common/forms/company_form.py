from django import forms
from common.models import Company

class CompanyForm(forms.ModelForm):
    """
    Form for creating and updating Companies.
    Styled for the Emerald Green glassmorphism theme.
    """
    class Meta:
        model = Company
        fields = [
            'name', 'code', 'express_database_name',
            'tax_id', 'address', 'phone', 'email', 'note', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Thai Jintan Co., Ltd.',
                'class': 'form-input'
            }),
            'code': forms.TextInput(attrs={
                'placeholder': 'e.g. TJ',
                'class': 'form-input uppercase'
            }),
            'express_database_name': forms.TextInput(attrs={
                'placeholder': 'e.g. TJ69',
                'class': 'form-input uppercase'
            }),
            'tax_id': forms.TextInput(attrs={
                'placeholder': 'Tax ID / VAT Number',
                'class': 'form-input'
            }),
            'address': forms.Textarea(attrs={
                'placeholder': 'Registered company address...',
                'rows': 3,
                'class': 'form-textarea'
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '+66...',
                'class': 'form-input'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'info@company.com',
                'class': 'form-input'
            }),
            'note': forms.Textarea(attrs={
                'placeholder': 'Internal notes...',
                'rows': 3,
                'class': 'form-textarea'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.upper().strip()
        return code

    def clean_express_database_name(self):
        db_name = self.cleaned_data.get('express_database_name')
        if db_name:
            return db_name.upper().strip()
        return db_name
