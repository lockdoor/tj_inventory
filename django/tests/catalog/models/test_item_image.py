"""
Tests for ItemImage Model

Tests cover:
- Basic CRUD with image file
- is_main flag
- sort_order
- CASCADE on item delete
- filename / extension properties
- __str__ representation
- Inherited mixin behaviour
"""

import pytest
import tempfile
from PIL import Image as PILImage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User

from catalog.models import Category, Item, ItemImage


def create_test_image(name="test.jpg", size=(100, 100), format="JPEG"):
    """Helper: generate a minimal in-memory image file."""
    import io
    img = PILImage.new("RGB", size, color="red")
    buffer = io.BytesIO()
    img.save(buffer, format=format)
    buffer.seek(0)
    return SimpleUploadedFile(
        name=name,
        content=buffer.read(),
        content_type=f"image/{format.lower()}"
    )


# ---------- Fixtures ----------
@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        username="admin", password="admin123", is_staff=True,
    )


@pytest.fixture
def item(db, admin_user):
    cat = Category.objects.create(
        name="Electronics", code="ELEC", created_by=admin_user,
    )
    return Item.objects.create(
        sku="IMG-ITEM-001",
        name="Camera",
        unit="pcs",
        category=cat,
        created_by=admin_user,
    )


@pytest.fixture
def main_image(db, admin_user, item, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return ItemImage.objects.create(
        item=item,
        image=create_test_image("main.jpg"),
        is_main=True,
        created_by=admin_user,
    )


@pytest.fixture
def secondary_image(db, admin_user, item, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    return ItemImage.objects.create(
        item=item,
        image=create_test_image("second.jpg"),
        is_main=False,
        created_by=admin_user,
    )


# ============================================================
# Basic CRUD
# ============================================================
class TestItemImageCRUD:

    def test_create_image(self, main_image, item):
        assert main_image.pk is not None
        assert main_image.item == item

    def test_str_representation_main(self, main_image):
        assert "(Main)" in str(main_image)

    def test_str_representation_secondary(self, secondary_image):
        assert "(Main)" not in str(secondary_image)

    def test_note_defaults_to_empty(self, main_image):
        assert main_image.note == ''


# ============================================================
# is_main Flag
# ============================================================
class TestIsMainFlag:

    def test_main_image_is_main(self, main_image):
        assert main_image.is_main is True

    def test_secondary_image_is_not_main(self, secondary_image):
        assert secondary_image.is_main is False

    def test_item_has_main_image(self, item, main_image):
        assert item.has_main_image is True

    def test_item_main_image_returns_correct(self, item, main_image, secondary_image):
        assert item.main_image == main_image

    def test_item_main_image_fallback_to_first(self, item, secondary_image):
        """When no is_main=True, main_image property returns first image."""
        assert item.main_image == secondary_image


# ============================================================
# CASCADE on Item Delete
# ============================================================
class TestCascadeDelete:

    def test_images_deleted_when_item_hard_deleted(
        self, item, main_image, secondary_image
    ):
        item_pk = item.pk
        item.hard_delete()
        assert ItemImage.objects.filter(item_id=item_pk).count() == 0


# ============================================================
# File Properties
# ============================================================
class TestFileProperties:

    def test_filename_is_not_none(self, main_image):
        assert main_image.filename is not None

    def test_extension_is_jpg(self, main_image):
        assert main_image.extension == '.jpg'


# ============================================================
# Inherited Mixin Behaviour
# ============================================================
class TestItemImageMixins:

    def test_default_status_active(self, main_image):
        assert main_image.is_active is True

    def test_deactivate_image(self, main_image):
        main_image.deactivate()
        main_image.refresh_from_db()
        assert main_image.is_active is False

    def test_soft_delete_image(self, main_image, admin_user):
        main_image.delete(user=admin_user)
        main_image.refresh_from_db()
        assert main_image.is_deleted is True

    def test_audit_created_at(self, main_image):
        assert main_image.created_at is not None

    def test_history_tracked(self, main_image):
        assert main_image.history.count() >= 1
