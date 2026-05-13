from django import forms
from ..models.attachment import PurchaseOrderAttachment, ArrivalAttachment

class PurchaseOrderAttachmentForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrderAttachment
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

class ArrivalAttachmentForm(forms.ModelForm):
    class Meta:
        model = ArrivalAttachment
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
