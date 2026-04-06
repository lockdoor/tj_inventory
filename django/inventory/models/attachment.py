from django.db import models
from common.mixins import AuditableMixin

class InventoryMovementAttachment(AuditableMixin):
    """
    Supporting file attachments for movement documents (e.g. Invoices, Photos).
    """
    movement = models.ForeignKey(
        'inventory.InventoryMovement',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    document_file = models.FileField(
        upload_to='inventory/attachments/%Y/%m/',
        help_text="Uploaded file (PDF, Image, etc.)"
    )
    file_name = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Original file name"
    )
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Optional remarks for this attachment"
    )

    class Meta:
        verbose_name = "Movement Attachment"
        verbose_name_plural = "Movement Attachments"

    def __str__(self):
        return f"{self.movement.document_no} - {self.file_name or self.document_file.name}"

    def save(self, *args, **kwargs):
        """Save basic file metadata if missing."""
        if not self.file_name and self.document_file:
            self.file_name = self.document_file.name
        super().save(*args, **kwargs)
