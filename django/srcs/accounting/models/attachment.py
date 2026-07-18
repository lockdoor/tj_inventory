from django.db import models
from common.mixins import AuditableMixin


class PettyCashPaymentAttachment(AuditableMixin):
    """
    Supporting file attachments for petty cash payment vouchers (e.g. physical receipts).
    """
    payment = models.ForeignKey(
        'accounting.PettyCashPayment',
        on_delete=models.CASCADE,
        related_name='attachments',
        help_text="Header payment document"
    )
    document_file = models.FileField(
        upload_to='accounting/attachments/%Y/%m/',
        help_text="Uploaded file (PDF, image, etc.)"
    )
    file_name = models.CharField(
        max_length=255, 
        blank=True, 
        help_text="Original filename"
    )
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Optional remarks for this attachment"
    )

    class Meta:
        verbose_name = "Petty Cash Payment Attachment"
        verbose_name_plural = "Petty Cash Payment Attachments"

    def __str__(self):
        return f"{self.payment.payment_no} - {self.file_name or self.document_file.name}"

    def save(self, *args, **kwargs):
        """Save basic file metadata if missing."""
        if not self.file_name and self.document_file:
            self.file_name = self.document_file.name
        super().save(*args, **kwargs)
