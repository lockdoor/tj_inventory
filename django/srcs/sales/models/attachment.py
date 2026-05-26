from django.db import models
from common.mixins.auditable import AuditableMixin


class SalesOrderAttachment(AuditableMixin):
    """
    Supporting file attachments for Sales Orders (e.g. customer PO documents, signed terms).
    """
    sales_order = models.ForeignKey(
        'sales.SalesOrder',
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    document_file = models.FileField(
        upload_to='sales/so/%Y/%m/',
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
        verbose_name = "Sales Order Attachment"
        verbose_name_plural = "Sales Order Attachments"

    def __str__(self):
        return f"{self.sales_order.document_no} - {self.file_name or self.document_file.name}"

    def save(self, *args, **kwargs):
        if not self.file_name and self.document_file:
            self.file_name = self.document_file.name
        super().save(*args, **kwargs)
