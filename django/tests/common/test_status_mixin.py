"""
Tests for StatusMixin

Tests cover:
- Default status is 'active'
- activate() and deactivate() methods
- is_active property
- Status choices validation (invalid value rejected)
- Status persists through save/refresh cycle
"""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from common.models import SampleStatusItem
from common.mixins import StatusMixin


# ---------- Fixtures ----------
@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin",
        password="admin123",
        is_staff=True,
    )


@pytest.fixture
def status_item(db, admin_user):
    return SampleStatusItem.objects.create(
        name="Test Status Item",
        created_by=admin_user,
    )


# ============================================================
# Default Status
# ============================================================
class TestDefaultStatus:
    """Verify the default status behaviour."""

    def test_default_status_is_active(self, status_item):
        assert status_item.status == StatusMixin.Status.ACTIVE

    def test_default_is_active_property_is_true(self, status_item):
        assert status_item.is_active is True


# ============================================================
# Activate / Deactivate
# ============================================================
class TestActivateDeactivate:
    """Verify activate() and deactivate() helper methods."""

    def test_deactivate_sets_status_to_inactive(self, status_item):
        status_item.deactivate()
        status_item.refresh_from_db()
        assert status_item.status == StatusMixin.Status.INACTIVE

    def test_is_active_false_after_deactivate(self, status_item):
        status_item.deactivate()
        status_item.refresh_from_db()
        assert status_item.is_active is False

    def test_activate_restores_status_to_active(self, status_item):
        status_item.deactivate()
        status_item.activate()
        status_item.refresh_from_db()
        assert status_item.status == StatusMixin.Status.ACTIVE

    def test_is_active_true_after_reactivate(self, status_item):
        status_item.deactivate()
        status_item.activate()
        status_item.refresh_from_db()
        assert status_item.is_active is True


# ============================================================
# Status Choices
# ============================================================
class TestStatusChoices:
    """Verify TextChoices enum values and validation."""

    def test_active_choice_value(self):
        assert StatusMixin.Status.ACTIVE == 'active'

    def test_inactive_choice_value(self):
        assert StatusMixin.Status.INACTIVE == 'inactive'

    def test_active_choice_label(self):
        assert StatusMixin.Status.ACTIVE.label == 'Active'

    def test_inactive_choice_label(self):
        assert StatusMixin.Status.INACTIVE.label == 'Inactive'

    def test_choices_has_exactly_two_options(self):
        assert len(StatusMixin.Status.choices) == 2

    def test_invalid_status_fails_full_clean(self, status_item):
        """Setting an invalid status should fail Django model validation."""
        status_item.status = 'invalid_status'
        with pytest.raises(ValidationError):
            status_item.full_clean()


# ============================================================
# Persistence
# ============================================================
class TestStatusPersistence:
    """Verify status survives save/refresh cycle."""

    def test_inactive_status_persists_after_refresh(self, status_item):
        status_item.status = StatusMixin.Status.INACTIVE
        status_item.save()
        status_item.refresh_from_db()
        assert status_item.status == StatusMixin.Status.INACTIVE

    def test_status_change_is_tracked_in_history(self, status_item):
        initial_count = status_item.history.count()
        status_item.deactivate()
        assert status_item.history.count() == initial_count + 1
