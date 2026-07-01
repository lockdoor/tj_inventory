from django.db import models
from django.contrib.auth.models import User
from common.mixins import AuditableMixin


class Individual(AuditableMixin):
    """
    Represents a physical person (independent of role) with bilingual name support.
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='individual',
        help_text="Optional link to authentication user"
    )
    first_name_th = models.CharField(max_length=150, default='', help_text="First name in Thai")
    last_name_th = models.CharField(max_length=150, default='', help_text="Last name in Thai")
    first_name_en = models.CharField(max_length=150, blank=True, default='', help_text="First name in English")
    last_name_en = models.CharField(max_length=150, blank=True, default='', help_text="Last name in English")
    nickname = models.CharField(max_length=50, blank=True, default='', help_text="Nickname (Thai or English)")
    email = models.EmailField(blank=True, default='', help_text="Email address")
    phones = models.JSONField(default=list, blank=True, help_text="JSON array of phone numbers")

    class Meta:
        ordering = ['first_name_th', 'last_name_th']
        verbose_name = "Individual"
        verbose_name_plural = "Individuals"

    def __str__(self):
        th_name = f"{self.first_name_th} {self.last_name_th}".strip()
        if self.nickname:
            return f"{th_name} ({self.nickname})"
        return th_name or f"Individual #{self.id}"

    @property
    def full_name(self):
        """Return the formatted primary full name of the individual."""
        return str(self)

    def save(self, *args, **kwargs):
        """Normalize fields before saving."""
        if self.first_name_th:
            self.first_name_th = self.first_name_th.strip()
        if self.last_name_th:
            self.last_name_th = self.last_name_th.strip()
        if self.first_name_en:
            self.first_name_en = self.first_name_en.strip()
        if self.last_name_en:
            self.last_name_en = self.last_name_en.strip()
        if self.nickname:
            self.nickname = self.nickname.strip()
        if self.email:
            self.email = self.email.strip().lower()
        if not isinstance(self.phones, list):
            self.phones = []
        super().save(*args, **kwargs)
