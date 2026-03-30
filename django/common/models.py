from django.db import models
from common.mixins import AuditableMixin


class SampleItem(AuditableMixin):
    """
    A minimal concrete model used purely for testing AuditableMixin.
    This model creates a real DB table so we can exercise the
    abstract mixin's functionality in tests.
    """
    name = models.CharField(max_length=100)

    class Meta:
        app_label = "common"

    def __str__(self):
        return self.name
