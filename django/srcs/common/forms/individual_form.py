from django import forms
from django.contrib.auth.models import User
from common.models import Individual


class IndividualForm(forms.ModelForm):
    """
    Form for creating and updating Individuals with bilingual names and nickname.
    Styled for the Emerald Green glassmorphism theme.
    """
    phones = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'placeholder': 'e.g. +66898765432, +6621234567',
            'class': 'form-input'
        }),
        help_text="Separate multiple phone numbers with commas."
    )

    class Meta:
        model = Individual
        fields = [
            'first_name_th', 'last_name_th', 
            'first_name_en', 'last_name_en', 
            'nickname', 'user', 'email', 'phones'
        ]
        widgets = {
            'first_name_th': forms.TextInput(attrs={
                'placeholder': 'ชื่อจริง (ภาษาไทย)',
                'class': 'form-input'
            }),
            'last_name_th': forms.TextInput(attrs={
                'placeholder': 'นามสกุล (ภาษาไทย)',
                'class': 'form-input'
            }),
            'first_name_en': forms.TextInput(attrs={
                'placeholder': 'First Name (English)',
                'class': 'form-input'
            }),
            'last_name_en': forms.TextInput(attrs={
                'placeholder': 'Last Name (English)',
                'class': 'form-input'
            }),
            'nickname': forms.TextInput(attrs={
                'placeholder': 'ชื่อเล่น (Nickname)',
                'class': 'form-input'
            }),
            'user': forms.Select(attrs={
                'class': 'form-select'
            }),
            'email': forms.EmailInput(attrs={
                'placeholder': 'email@example.com',
                'class': 'form-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate initial value for phones CharField if instance exists
        if self.instance and self.instance.pk and isinstance(self.instance.phones, list):
            self.initial['phones'] = ', '.join(self.instance.phones)
            
        # Limit user choices to those not already linked to other Individuals
        linked_user_ids = Individual.objects.exclude(id=self.instance.id if self.instance and self.instance.id else None).values_list('user_id', flat=True)
        self.fields['user'].queryset = User.objects.exclude(id__in=linked_user_ids)
        self.fields['user'].empty_label = "--- No System User ---"

    def clean_phones(self):
        phones_str = self.cleaned_data.get('phones', '')
        if phones_str:
            # Split by commas and strip whitespace
            return [p.strip() for p in phones_str.split(',') if p.strip()]
        return []
