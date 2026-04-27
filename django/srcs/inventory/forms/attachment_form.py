from django import forms
from django.forms import inlineformset_factory
from inventory.models.attachment import InventoryMovementAttachment
from inventory.models.movement import InventoryMovement

class MovementAttachmentForm(forms.ModelForm):
    """
    Form for individual document attachments.
    """
    class Meta:
        model = InventoryMovementAttachment
        fields = ['document_file', 'note']
        widgets = {
            'document_file': forms.ClearableFileInput(attrs={
                'class': 'glass-input',
                'accept': '.pdf, .jpg, .jpeg, .png, .doc, .docx, .xls, .xlsx'
            }),
            'note': forms.TextInput(attrs={
                'class': 'glass-input',
                'placeholder': 'Description (e.g. Invoice #123)...'
            }),
        }

# No longer using formset, handling single uploads in detail view
