from django.db import models
from django.utils import timezone
from common.mixins import AuditableMixin


class PettyCashPayment(AuditableMixin):
    """
    Voucher documenting a payment, replenishment, or adjustment.
    """
    payment_no = models.CharField(
        max_length=50, 
        unique=True, 
        blank=True, 
        help_text="Unique auto-generated voucher number"
    )
    payment_type = models.CharField(
        max_length=30,
        choices=[
            ('disbursement', 'Disbursement'),
            ('replenishment', 'Replenishment'),
            ('adjustment', 'Adjustment')
        ],
        help_text="Transaction type"
    )
    total_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        default=0, 
        help_text="Sum of all payment line amounts and tax"
    )
    payment_date = models.DateField(default=timezone.now, help_text="Date when transaction occurred")
    account = models.ForeignKey(
        'accounting.PettyCashAccount', 
        on_delete=models.PROTECT, 
        related_name='payments',
        help_text="Associated petty cash box account"
    )
    payee = models.ForeignKey(
        'common.Individual', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='payments',
        help_text="Linked profile payee (optional)"
    )
    payee_name = models.CharField(
        max_length=255, 
        blank=True, 
        default='', 
        help_text="Custom payee name if not a registered individual"
    )
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Optional remarks for this payment"
    )
    is_posted = models.BooleanField(
        default=False,
        help_text="Designates whether this voucher has been posted/recorded in Express ERP."
    )
    posted_at = models.DateTimeField(null=True, blank=True)
    posted_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='posted_payments'
    )
    class Meta:
        ordering = ['-payment_date', '-id']
        verbose_name = "Petty Cash Payment"
        verbose_name_plural = "Petty Cash Payments"

    def __str__(self):
        return f"{self.payment_no} ({self.get_payment_type_display()}) - {self.total_amount}"

    def save(self, *args, **kwargs):
        """Auto-generate voucher number if empty and normalize."""
        if not self.payment_no:
            date_str = self.payment_date.strftime('%Y%m%d')
            prefix = f"PV-{date_str}-"
            count = PettyCashPayment.objects.filter(payment_no__startswith=prefix).count()
            self.payment_no = f"{prefix}{count + 1:04d}"
        if self.payee_name:
            self.payee_name = self.payee_name.strip()
        super().save(*args, **kwargs)


class PettyCashPaymentItem(models.Model):
    """
    Individual line items mapping payment breakdown to expense categories.
    """
    payment = models.ForeignKey(
        PettyCashPayment, 
        on_delete=models.CASCADE, 
        related_name='items',
        help_text="Header payment document"
    )
    description = models.TextField(blank=True, default='', help_text="Line item details")
    amount = models.DecimalField(max_digits=12, decimal_places=2, help_text="Item line amount")
    tax = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True, 
        help_text="TAX amount associated with this item"
    )
    category = models.ForeignKey(
        'accounting.PettyCashCategory', 
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_items',
        help_text="Bilingual category with accounting code mapping"
    )
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Optional remarks for this item"
    )
    external_pv_no = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="External Express PV (Payment Voucher) number if created directly in Express."
    )
    rounding_adjustment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Adjustment to round this item to integer"
    )

    class Meta:
        verbose_name = "Petty Cash Payment Item"
        verbose_name_plural = "Petty Cash Payment Items"

    def __str__(self):
        category_name = self.category.name if self.category else (f"PV: {self.external_pv_no}" if self.external_pv_no else "Unallocated")
        return f"{self.payment.payment_no} Line Item: {category_name} - {self.amount}"
