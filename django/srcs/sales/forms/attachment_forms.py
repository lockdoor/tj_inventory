from django import forms
from ..models.attachment import SalesOrderAttachment


class SalesOrderAttachmentForm(forms.ModelForm):
    class Meta:
        model = SalesOrderAttachment
        fields = ['document_file', 'note']
        widgets = {
            'document_file': forms.FileInput(attrs={
                'class': 'form-control-file',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx,.xls,.xlsx'
            }),
            'note': forms.TextInput(attrs={
                'class': 'form-control-mini',
                'placeholder': 'Description (optional)...'
            }),
        }
