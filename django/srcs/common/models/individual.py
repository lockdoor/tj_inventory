from django.db import models
from django.contrib.auth.models import User
from common.mixins import AuditableMixin


class Individual(AuditableMixin):
    """
    Represents a physical person (independent of role).
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='individual',
        help_text="Optional link to authentication user"
    )
    first_name = models.CharField(max_length=150, help_text="First name")
    last_name = models.CharField(max_length=150, help_text="Last name")
    email = models.EmailField(blank=True, default='', help_text="Email address")
    phones = models.JSONField(default=list, blank=True, help_text="JSON array of phone numbers")

    class Meta:
        ordering = ['first_name', 'last_name']
        verbose_name = "Individual"
        verbose_name_plural = "Individuals"

    def __str__(self):
        return f"{self.first_name} {self.last_name}".strip() or f"Individual #{self.id}"

    def save(self, *args, **kwargs):
        """Normalize fields before saving."""
        if self.first_name:
            self.first_name = self.first_name.strip()
        if self.last_name:
            self.last_name = self.last_name.strip()
        if self.email:
            self.email = self.email.strip().lower()
        if not isinstance(self.phones, list):
            self.phones = []
        super().save(*args, **kwargs)
