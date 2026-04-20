"""
Tests for Category Model

Tests cover:
- Basic CRUD (create, read, update)
- Unique code constraint
- Self-referencing parent (nested hierarchy)
- is_root property
- full_path property
- __str__ representation
- Children reverse relation
- PROTECT on parent delete
- Inherited mixin behaviour (audit fields, status, soft delete)
"""

import pytest
from django.db import IntegrityError
from django.contrib.auth.models import User

from catalog.models import Category


# ---------- Fixtures ----------
@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin",
        password="admin123",
        is_staff=True,
    )


@pytest.fixture
def root_category(db, admin_user):
    return Category.objects.create(
        name="Electronics",
        code="ELEC",
        created_by=admin_user,
    )


@pytest.fixture
def child_category(db, admin_user, root_category):
    return Category.objects.create(
        name="Smartphones",
        code="SMART",
        parent=root_category,
        created_by=admin_user,
    )


@pytest.fixture
def grandchild_category(db, admin_user, child_category):
    return Category.objects.create(
        name="Android",
        code="ANDRO",
        parent=child_category,
        created_by=admin_user,
    )


# ============================================================
# Basic CRUD
# ============================================================
class TestCategoryCRUD:
    """Verify basic create, read, update operations."""

    def test_create_category(self, root_category):
        assert root_category.pk is not None
        assert root_category.name == "Electronics"
        assert root_category.code == "ELEC"

    def test_read_category_from_db(self, root_category):
        fetched = Category.objects.get(pk=root_category.pk)
        assert fetched.name == "Electronics"
        assert fetched.code == "ELEC"

    def test_update_category_name(self, root_category):
        root_category.name = "Consumer Electronics"
        root_category.save()
        root_category.refresh_from_db()
        assert root_category.name == "Consumer Electronics"

    def test_str_representation(self, root_category):
        assert str(root_category) == "ELEC - Electronics"

    def test_note_defaults_to_empty(self, root_category):
        assert root_category.note == ''

    def test_note_can_be_set(self, root_category):
        root_category.note = "Main electronics category"
        root_category.save()
        root_category.refresh_from_db()
        assert root_category.note == "Main electronics category"


# ============================================================
# Unique Code Constraint
# ============================================================
class TestUniqueCode:
    """Verify the unique constraint on the code field."""

    def test_duplicate_code_raises_integrity_error(self, root_category, admin_user):
        with pytest.raises(IntegrityError):
            Category.objects.create(
                name="Another Category",
                code="ELEC",  # same code as root_category
                created_by=admin_user,
            )

    def test_different_codes_are_allowed(self, root_category, admin_user):
        other = Category.objects.create(
            name="Clothing",
            code="CLOTH",
            created_by=admin_user,
        )
        assert other.pk is not None
        assert other.code != root_category.code


# ============================================================
# Nested Hierarchy (parent / children)
# ============================================================
class TestNestedHierarchy:
    """Verify self-referencing parent-child relationships."""

    def test_root_category_has_no_parent(self, root_category):
        assert root_category.parent is None

    def test_child_has_parent(self, child_category, root_category):
        assert child_category.parent == root_category

    def test_children_reverse_relation(self, root_category, child_category):
        assert child_category in root_category.children.all()

    def test_root_has_correct_children_count(self, root_category, child_category):
        assert root_category.children.count() == 1

    def test_grandchild_has_correct_parent(self, grandchild_category, child_category):
        assert grandchild_category.parent == child_category

    def test_delete_parent_with_children_raises_protected_error(
        self, root_category, child_category
    ):
        """PROTECT should prevent deleting a parent that has children."""
        from django.db.models import ProtectedError
        with pytest.raises(ProtectedError):
            root_category.hard_delete()


# ============================================================
# is_root Property
# ============================================================
class TestIsRoot:
    """Verify the is_root property."""

    def test_root_category_is_root(self, root_category):
        assert root_category.is_root is True

    def test_child_category_is_not_root(self, child_category):
        assert child_category.is_root is False

    def test_grandchild_is_not_root(self, grandchild_category):
        assert grandchild_category.is_root is False


# ============================================================
# full_path Property
# ============================================================
class TestFullPath:
    """Verify the full_path breadcrumb property."""

    def test_root_full_path(self, root_category):
        assert root_category.full_path == "Electronics"

    def test_child_full_path(self, child_category):
        assert child_category.full_path == "Electronics > Smartphones"

    def test_grandchild_full_path(self, grandchild_category):
        assert grandchild_category.full_path == "Electronics > Smartphones > Android"


# ============================================================
# Inherited Mixin Behaviour
# ============================================================
class TestInheritedMixins:
    """Verify that AuditableMixin and StatusMixin work on Category."""

    # --- AuditableMixin ---
    def test_audit_created_at_is_set(self, root_category):
        assert root_category.created_at is not None

    def test_audit_created_by_is_set(self, root_category, admin_user):
        assert root_category.created_by == admin_user

    def test_version_starts_at_1(self, root_category):
        assert root_category.version == 1

    def test_version_increments_on_save(self, root_category):
        root_category.name = "Updated"
        root_category.save()
        root_category.refresh_from_db()
        assert root_category.version == 2

    # --- StatusMixin ---
    def test_default_status_is_active(self, root_category):
        assert root_category.is_active is True

    def test_deactivate_category(self, root_category):
        root_category.deactivate()
        root_category.refresh_from_db()
        assert root_category.is_active is False

    def test_reactivate_category(self, root_category):
        root_category.deactivate()
        root_category.activate()
        root_category.refresh_from_db()
        assert root_category.is_active is True

    # --- Soft Delete ---
    def test_soft_delete_category(self, root_category, admin_user):
        root_category.delete(user=admin_user)
        root_category.refresh_from_db()
        assert root_category.is_deleted is True

    def test_restore_category(self, root_category, admin_user):
        root_category.delete(user=admin_user)
        root_category.restore()
        root_category.refresh_from_db()
        assert root_category.is_deleted is False

    # --- History ---
    def test_history_is_tracked(self, root_category):
        assert root_category.history.count() >= 1
