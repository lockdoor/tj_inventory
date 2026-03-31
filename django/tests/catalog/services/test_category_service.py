"""
Tests for CategoryService

Tests cover:
- Create functionality
- Update functionality
- Soft delete business rules (blocked if active children)

Note: Permission checks are NOT tested here.
      They will be tested at the View/API layer.
"""

import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User

from catalog.models import Category
from catalog.services import CategoryService


# ---------- Fixtures ----------
@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin", password="admin123", is_staff=True,
    )


@pytest.fixture
def root(db, admin_user):
    return Category.objects.create(
        name="Electronics", code="ELEC", created_by=admin_user,
    )


@pytest.fixture
def child(db, admin_user, root):
    return Category.objects.create(
        name="Smartphones", code="SMART", parent=root, created_by=admin_user,
    )


# ============================================================
# Create
# ============================================================
class TestCreate:

    def test_create_category(self, admin_user):
        cat = CategoryService.create(
            name="Toys", code="TOY", user=admin_user,
        )
        assert cat.pk is not None
        assert cat.name == "Toys"
        assert cat.code == "TOY"

    def test_create_sets_created_by(self, admin_user):
        cat = CategoryService.create(
            name="Toys", code="TOY", user=admin_user,
        )
        assert cat.created_by == admin_user

    def test_create_with_parent(self, admin_user, root):
        cat = CategoryService.create(
            name="Laptops", code="LAP", user=admin_user, parent=root,
        )
        assert cat.parent == root

    def test_create_with_note(self, admin_user):
        cat = CategoryService.create(
            name="Food", code="FOOD", user=admin_user, note="Perishable items",
        )
        assert cat.note == "Perishable items"

    def test_create_validates_before_save(self, admin_user, root):
        """Duplicate code should raise ValidationError via full_clean."""
        with pytest.raises(ValidationError):
            CategoryService.create(
                name="Duplicate", code="ELEC", user=admin_user,
            )


# ============================================================
# Update
# ============================================================
class TestUpdate:

    def test_update_name(self, admin_user, root):
        CategoryService.update(root, user=admin_user, name="Consumer Electronics")
        root.refresh_from_db()
        assert root.name == "Consumer Electronics"

    def test_update_sets_updated_by(self, admin_user, root):
        CategoryService.update(root, user=admin_user, name="New Name")
        root.refresh_from_db()
        assert root.updated_by == admin_user

    def test_update_multiple_fields(self, admin_user, root):
        CategoryService.update(
            root, user=admin_user, name="Updated", note="Changed",
        )
        root.refresh_from_db()
        assert root.name == "Updated"
        assert root.note == "Changed"

    def test_update_ignores_unknown_fields(self, admin_user, root):
        original_name = root.name
        CategoryService.update(root, user=admin_user, fake_field="ignored")
        root.refresh_from_db()
        assert root.name == original_name


# ============================================================
# Soft Delete — Business Rules
# ============================================================
class TestSoftDelete:

    def test_delete_leaf_category(self, admin_user, root):
        CategoryService.soft_delete(root, user=admin_user)
        root.refresh_from_db()
        assert root.is_deleted is True

    def test_delete_sets_deleted_by(self, admin_user, root):
        CategoryService.soft_delete(root, user=admin_user)
        root.refresh_from_db()
        assert root.deleted_by == admin_user

    def test_blocked_when_has_active_children(self, admin_user, root, child):
        with pytest.raises(ValidationError, match="active children"):
            CategoryService.soft_delete(root, user=admin_user)

    def test_parent_not_deleted_when_blocked(self, admin_user, root, child):
        with pytest.raises(ValidationError):
            CategoryService.soft_delete(root, user=admin_user)
        root.refresh_from_db()
        assert root.is_deleted is False

    def test_allowed_when_children_already_deleted(self, admin_user, root, child):
        CategoryService.soft_delete(child, user=admin_user)
        CategoryService.soft_delete(root, user=admin_user)
        root.refresh_from_db()
        assert root.is_deleted is True

    def test_error_includes_child_names(self, admin_user, root, child):
        with pytest.raises(ValidationError, match="Smartphones"):
            CategoryService.soft_delete(root, user=admin_user)
