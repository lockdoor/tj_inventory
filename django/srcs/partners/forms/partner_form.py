from django import forms
from partners.models import Partner

class PartnerForm(forms.ModelForm):
    """
    Form for creating and updating Partners.
    Styled for the Emerald Green glassmorphism theme.
    """
    class Meta:
        model = Partner
        fields = [
            'name', 'code', 'is_supplier', 'is_customer', 
            'tax_id', 'address', 'contact_name', 'phone', 
            'email', 'note', 'status'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'placeholder': 'e.g. Acme Corp',
                'class': 'form-input'
            }),
            'code': forms.TextInput(attrs={
                'placeholder': 'e.g. ACME-01',
                'class': 'form-input uppercase'
            }),
            'is_supplier': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
            'is_customer': forms.CheckboxInput(attrs={
                'class': 'form-checkbox'
            }),
            'tax_id': forms.TextInput(attrs={
                'placeholder': 'Tax ID / VAT Number',
                'class': 'form-input'
            }),
            'address': forms.Textarea(attrs={
                'placeholder': 'Physical or billing address...',
                'rows': 3,
                'class': 'form-textarea'
            }),
            'contact_name': forms.TextInput(attrs={
                'placeholder': 'Point of contact person',
                'class': 'form-input'
            }),
            'phone': forms.TextInput(attrs={
                'placeholder': '+66...',
                'class': 'form-input'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'contact@company.com',
                'class': 'form-input'
            }),
            'note': forms.Textarea(attrs={
                'placeholder': 'Internal notes or terms...',
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
