from django.db import models
from common.mixins import AuditableMixin


class PettyCashCategory(AuditableMixin):
    """
    Binds a user-friendly expense category and its accounting code (Chart of Accounts / ผังบัญชี)
    to a legal entity (Company).
    """
    code = models.CharField(max_length=50, help_text="GL Account Code (e.g. 5101-01)")
    name = models.CharField(max_length=200, help_text="Category Name (e.g. Travel Expenses)")
    company = models.ForeignKey(
        'common.Company', 
        on_delete=models.CASCADE, 
        related_name='expense_categories',
        help_text="Owning company legal entity"
    )

    class Meta:
        ordering = ['code']
        verbose_name = "Petty Cash Category"
        verbose_name_plural = "Petty Cash Categories"
        unique_together = ('company', 'code')

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        """Normalize code and name inputs."""
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)
