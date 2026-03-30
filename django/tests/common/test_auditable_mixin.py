"""
Tests for AuditableMixin

Tests cover:
- Audit fields (created_at, created_by, updated_at, updated_by)
- Soft delete (delete, is_deleted, deleted_at, deleted_by)
- Restore after soft delete
- Hard delete (physical deletion)
- Optimistic locking (version conflict detection)
- Version refresh
- History tracking via django-simple-history
"""

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from common.models import SampleItem


# ---------- Fixtures ----------
@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin",
        password="admin123",
        is_staff=True,
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="other",
        password="other123",
    )


@pytest.fixture
def sample_item(db, admin_user):
    return SampleItem.objects.create(
        name="Test Item",
        created_by=admin_user,
    )


# ============================================================
# Audit Fields
# ============================================================
class TestAuditFields:
    """Verify that audit timestamp and user fields are populated."""

    def test_created_at_is_auto_set(self, sample_item):
        assert sample_item.created_at is not None

    def test_created_by_is_set(self, sample_item, admin_user):
        assert sample_item.created_by == admin_user

    def test_updated_at_is_auto_set(self, sample_item):
        assert sample_item.updated_at is not None

    def test_updated_by_defaults_to_none(self, sample_item):
        assert sample_item.updated_by is None

    def test_updated_by_is_tracked(self, sample_item, other_user):
        sample_item.updated_by = other_user
        sample_item.save()
        sample_item.refresh_from_db()
        assert sample_item.updated_by == other_user


# ============================================================
# Soft Delete
# ============================================================
class TestSoftDelete:
    """Verify soft-delete, restore, and hard-delete behaviour."""

    def test_is_deleted_defaults_to_false(self, sample_item):
        assert sample_item.is_deleted is False

    def test_soft_delete_sets_is_deleted(self, sample_item, admin_user):
        sample_item.delete(user=admin_user)
        sample_item.refresh_from_db()
        assert sample_item.is_deleted is True

    def test_soft_delete_sets_deleted_at(self, sample_item, admin_user):
        sample_item.delete(user=admin_user)
        sample_item.refresh_from_db()
        assert sample_item.deleted_at is not None

    def test_soft_delete_sets_deleted_by(self, sample_item, admin_user):
        sample_item.delete(user=admin_user)
        sample_item.refresh_from_db()
        assert sample_item.deleted_by == admin_user

    def test_soft_delete_does_not_remove_from_db(self, sample_item, admin_user):
        pk = sample_item.pk
        sample_item.delete(user=admin_user)
        assert SampleItem.objects.filter(pk=pk).exists()

    def test_restore_clears_soft_delete_fields(self, sample_item, admin_user):
        sample_item.delete(user=admin_user)
        sample_item.restore()
        sample_item.refresh_from_db()
        assert sample_item.is_deleted is False
        assert sample_item.deleted_at is None
        assert sample_item.deleted_by is None

    def test_hard_delete_removes_from_db(self, sample_item):
        pk = sample_item.pk
        sample_item.hard_delete()
        assert not SampleItem.objects.filter(pk=pk).exists()


# ============================================================
# Optimistic Locking
# ============================================================
class TestOptimisticLocking:
    """Verify version-based optimistic locking."""

    def test_initial_version_is_1(self, sample_item):
        assert sample_item.version == 1

    def test_version_increments_on_save(self, sample_item):
        sample_item.name = "Updated"
        sample_item.save()
        sample_item.refresh_from_db()
        assert sample_item.version == 2

    def test_stale_version_raises_validation_error(self, sample_item):
        """Simulate two users loading the same record, then both saving."""
        # User A loads the record
        user_a_copy = SampleItem.objects.get(pk=sample_item.pk)

        # User B loads the same record and saves first
        user_b_copy = SampleItem.objects.get(pk=sample_item.pk)
        user_b_copy.name = "User B change"
        user_b_copy.save()  # version becomes 2

        # User A now tries to save with the stale version (1)
        user_a_copy.name = "User A change"
        with pytest.raises(ValidationError, match="modified by another user"):
            user_a_copy.save()

    def test_refresh_version_updates_to_latest(self, sample_item):
        # Save once to bump version to 2
        sample_item.name = "v2"
        sample_item.save()

        # Create a stale copy
        stale = SampleItem.objects.get(pk=sample_item.pk)
        stale.version = 1  # pretend stale

        refreshed = stale.refresh_version()
        assert refreshed == 2
        assert stale.version == 2


# ============================================================
# History Tracking
# ============================================================
class TestHistoryTracking:
    """Verify django-simple-history records changes."""

    def test_history_is_created_on_save(self, sample_item):
        assert sample_item.history.count() >= 1

    def test_history_records_update(self, sample_item):
        initial_count = sample_item.history.count()
        sample_item.name = "Changed"
        sample_item.save()
        assert sample_item.history.count() == initial_count + 1

    def test_history_stores_old_value(self, sample_item):
        original_name = sample_item.name
        sample_item.name = "New Name"
        sample_item.save()
        previous = sample_item.history.all()[1]  # second-most-recent
        assert previous.name == original_name
