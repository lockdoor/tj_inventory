"""
Tests for Item Model

Tests cover:
- Basic CRUD
- Unique SKU constraint
- Category relationship (SET_NULL behaviour)
- Field normalization (strip whitespace on save)
- express_sku optional
- main_image / has_main_image properties
- __str__ representation
- Inherited mixin behaviour (audit, status, soft delete)
"""

import pytest
from django.db import IntegrityError
from django.contrib.auth.models import User

from catalog.models import Category, Item


# ---------- Fixtures ----------
@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin", password="admin123", is_staff=True,
    )


@pytest.fixture
def category(db, admin_user):
    return Category.objects.create(
        name="Electronics", code="ELEC", created_by=admin_user,
    )


@pytest.fixture
def item(db, admin_user, category):
    return Item.objects.create(
        sku="ITEM-001",
        name="Widget A",
        unit="pcs",
        category=category,
        created_by=admin_user,
    )


@pytest.fixture
def item_no_category(db, admin_user):
    return Item.objects.create(
        sku="ITEM-NOCAT",
        name="Standalone Widget",
        unit="kg",
        created_by=admin_user,
    )


# ============================================================
# Basic CRUD
# ============================================================
class TestItemCRUD:

    def test_create_item(self, item):
        assert item.pk is not None
        assert item.sku == "ITEM-001"
        assert item.name == "Widget A"
        assert item.unit == "pcs"

    def test_str_representation(self, item):
        assert str(item) == "ITEM-001 - Widget A"

    def test_update_item_name(self, item):
        item.name = "Widget B"
        item.save()
        item.refresh_from_db()
        assert item.name == "Widget B"

    def test_note_defaults_to_empty(self, item):
        assert item.note == ''


    def test_express_sku_defaults_to_empty(self, item):
        assert item.express_sku == ''

    def test_express_sku_can_be_set(self, item):
        item.express_sku = "EXP-001"
        item.save()
        item.refresh_from_db()
        assert item.express_sku == "EXP-001"


# ============================================================
# Unique SKU
# ============================================================
class TestUniqueSKU:

    def test_duplicate_sku_raises_integrity_error(self, item, admin_user):
        with pytest.raises(IntegrityError):
            Item.objects.create(
                sku="ITEM-001",
                name="Duplicate",
                unit="pcs",
                created_by=admin_user,
            )

    def test_different_skus_allowed(self, item, admin_user):
        other = Item.objects.create(
            sku="ITEM-002",
            name="Other Widget",
            unit="pcs",
            created_by=admin_user,
        )
        assert other.pk is not None


# ============================================================
# Category Relationship
# ============================================================
class TestCategoryRelationship:

    def test_item_has_category(self, item, category):
        assert item.category == category

    def test_item_in_category_items(self, item, category):
        assert item in category.items.all()

    def test_item_can_have_no_category(self, item_no_category):
        assert item_no_category.category is None

    def test_category_delete_sets_item_category_null(self, item, category):
        """SET_NULL: deleting the category should null the item's FK, not crash."""
        category.hard_delete()
        item.refresh_from_db()
        assert item.category is None


# ============================================================
# Field Normalization
# ============================================================
class TestFieldNormalization:

    def test_sku_is_stripped_on_save(self, admin_user):
        item = Item.objects.create(
            sku="  ITEM-SPACE  ",
            name="  Spaced Widget  ",
            unit="  pcs  ",
            created_by=admin_user,
        )
        item.refresh_from_db()
        assert item.sku == "ITEM-SPACE"
        assert item.name == "Spaced Widget"
        assert item.unit == "pcs"


# ============================================================
# Image Properties (without actual images)
# ============================================================
class TestImageProperties:

    def test_has_main_image_false_when_no_images(self, item):
        assert item.has_main_image is False

    def test_main_image_none_when_no_images(self, item):
        assert item.main_image is None


# ============================================================
# Inherited Mixin Behaviour
# ============================================================
class TestItemMixins:

    def test_audit_created_at(self, item):
        assert item.created_at is not None

    def test_default_status_active(self, item):
        assert item.is_active is True

    def test_deactivate_item(self, item):
        item.deactivate()
        item.refresh_from_db()
        assert item.is_active is False

    def test_soft_delete_item(self, item, admin_user):
        item.delete(user=admin_user)
        item.refresh_from_db()
        assert item.is_deleted is True

    def test_version_starts_at_1(self, item):
        assert item.version == 1

    def test_history_tracked(self, item):
        assert item.history.count() >= 1
