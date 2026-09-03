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
    note = models.TextField(
        blank=True, 
        default='', 
        help_text="Optional remarks for this category"
    )

    class Meta:
        ordering = ['code']
        verbose_name = "Petty Cash Category"
        verbose_name_plural = "Petty Cash Categories"
        unique_together = ('company', 'code')

    @property
    def level(self):
        """
        Calculate hierarchical indent level based on GL code format.
        Level 1: XXX000-00 (ends in 000-00)
        Level 2: XXXX00-00 (ends in 00-00)
        Level 3: XXXXX0-00 (ends in 0-00)
        Level 4: XXXXXX-00 (ends in -00)
        Level 5: XXXXXX-XX (any other suffix)
        """
        if not self.code:
            return 1
        code_clean = self.code.strip().replace('-', '')
        if len(code_clean) < 6:
            return 1
        if code_clean.endswith('00000'):
            return 1
        if code_clean.endswith('0000'):
            return 2
        if code_clean.endswith('000'):
            return 3
        if code_clean.endswith('00'):
            return 4
        return 5

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        """Normalize code and name inputs."""
        if self.code:
            self.code = self.code.strip().upper()
        if self.name:
            self.name = self.name.strip()
        super().save(*args, **kwargs)
