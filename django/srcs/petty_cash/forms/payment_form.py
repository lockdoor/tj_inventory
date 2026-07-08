from django import forms
from django.forms.models import inlineformset_factory, BaseInlineFormSet
from petty_cash.models import PettyCashPayment, PettyCashPaymentItem


class PettyCashPaymentForm(forms.ModelForm):
    class Meta:
        model = PettyCashPayment
        fields = ['payment_type', 'payee', 'payee_name', 'payment_date', 'note']
        widgets = {
            'payment_type': forms.Select(attrs={'class': 'form-input'}),
            'payee': forms.Select(attrs={'class': 'form-input'}),
            'payee_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Somchai S.'}),
            'payment_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'note': forms.Textarea(attrs={'class': 'form-input', 'rows': 3, 'placeholder': 'Optional remarks...'}),
        }

    def clean_payee_name(self):
        payee_name = self.cleaned_data.get('payee_name')
        if payee_name:
            return payee_name.strip()
        return payee_name


class PettyCashPaymentItemForm(forms.ModelForm):
    class Meta:
        model = PettyCashPaymentItem
        fields = ['category', 'description', 'amount', 'note']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-input'}),
            'description': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Office files'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'}),
            'note': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Optional line note...'}),
        }

    def __init__(self, *args, **kwargs):
        company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        self.fields['category'].empty_label = "Unallocated (Pending Review)"
        if company:
            self.fields['category'].queryset = self.fields['category'].queryset.filter(
                company=company, is_deleted=False
            )


class BasePaymentItemFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        self.company = kwargs.pop('company', None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['company'] = self.company
        return super()._construct_form(i, **kwargs)


PettyCashPaymentItemFormSet = inlineformset_factory(
    PettyCashPayment,
    PettyCashPaymentItem,
    form=PettyCashPaymentItemForm,
    formset=BasePaymentItemFormSet,
    extra=1,
    can_delete=True
)
