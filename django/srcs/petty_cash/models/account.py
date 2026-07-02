from django.db import models
from django.contrib.auth.models import User
from common.mixins import AuditableMixin


class PettyCashAccount(AuditableMixin):
    """
    A cash box owned by a legal entity and managed by a custodian.
    """
    code = models.CharField(max_length=50, unique=True, help_text="Unique cash box code (e.g. PC-TJ)")
    name = models.CharField(max_length=200, help_text="Display name")
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text="Current cash balance")
    max_limit = models.DecimalField(max_digits=12, decimal_places=2, help_text="Maximum ceiling limit")
    currency = models.CharField(max_length=10, default='THB', help_text="Voucher currency")
    status = models.CharField(
        max_length=20, 
        choices=[('active', 'Active'), ('inactive', 'Inactive')], 
        default='active', 
        help_text="Account status"
    )
    company = models.ForeignKey(
        'common.Company', 
        on_delete=models.PROTECT, 
        related_name='petty_cash_accounts',
        help_text="Owning company legal entity"
    )
    custodian = models.ForeignKey(
        User, 
        on_delete=models.PROTECT, 
        related_name='custodian_accounts',
        help_text="Custodian user responsible for the cash box"
    )

    class Meta:
        ordering = ['code']
        verbose_name = "Petty Cash Account"
        verbose_name_plural = "Petty Cash Accounts"

    def __str__(self):
        return f"{self.code} - {self.name} ({self.custodian.username})"

    def save(self, *args, **kwargs):
        """Normalize code and name inputs."""
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)
