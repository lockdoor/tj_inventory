from django import forms
from django.core.exceptions import ValidationError
from accounting.models import PettyCashAccount


class PettyCashAccountForm(forms.ModelForm):
    currency = forms.ChoiceField(
        choices=[
            ('THB', 'THB - Thai Baht'),
            ('USD', 'USD - US Dollar'),
            ('EUR', 'EUR - Euro'),
            ('JPY', 'JPY - Japanese Yen'),
        ],
        widget=forms.Select(attrs={'class': 'form-input'})
    )

    class Meta:
        model = PettyCashAccount
        fields = ['code', 'name', 'max_limit', 'balance', 'currency', 'company', 'custodian', 'status', 'note']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. PC-HO-01'}),
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Head Office Cash Box'}),
            'max_limit': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'balance': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'company': forms.Select(attrs={'class': 'form-input'}),
            'custodian': forms.Select(attrs={'class': 'form-input'}),
            'status': forms.Select(attrs={'class': 'form-input'}),
            'note': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional details...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Disallow custodian modifications on update
        if self.instance and self.instance.pk:
            self.fields['custodian'].disabled = True
            self.fields['company'].disabled = True
            # balance should also be read-only on update as it is altered via payments
            self.fields['balance'].disabled = True

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            return code.strip().upper()
        return code
