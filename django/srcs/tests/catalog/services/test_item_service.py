import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from catalog.models import Item, Category
from catalog.services import ItemService

@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='password123')

@pytest.fixture
def category(db, user):
    return Category.objects.create(name='Test Category', code='TC', created_by=user)

@pytest.mark.django_db
class TestItemService:
    """
    Unit tests for ItemService business logic.
    Focuses on SKU uniqueness, status tracking, and audit fields.
    """

    def test_create_item_success(self, user, category):
        item = ItemService.create(
            sku='SKU001',
            name='Test Item',
            unit='Pcs',
            user=user,
            category=category,
            note='Sample note'
        )
        assert item.pk is not None
        assert item.sku == 'SKU001'
        assert item.category == category
        assert item.created_by == user
        assert item.is_deleted is False

    def test_create_item_duplicate_sku_fails(self, user, category):
        ItemService.create(sku='DUP-SKU', name='First', unit='Pcs', user=user)
        with pytest.raises(ValidationError):
            ItemService.create(sku='DUP-SKU', name='Second', unit='Pcs', user=user)

    def test_update_item_success(self, user, category):
        item = ItemService.create(sku='OLD-SKU', name='Old Name', unit='Unit', user=user)
        
        updated_item = ItemService.update(
            item,
            user=user,
            name='New Name',
            sku='NEW-SKU',
            category=category
        )
        
        assert updated_item.name == 'New Name'
        assert updated_item.sku == 'NEW-SKU'
        assert updated_item.category == category
        assert updated_item.updated_by == user

    def test_soft_delete_success(self, user):
        item = ItemService.create(sku='DEL-ME', name='Delete Item', unit='Pcs', user=user)
        
        ItemService.soft_delete(item, user=user)
        
        item.refresh_from_db()
        assert item.is_deleted is True
        assert item.deleted_by == user
        assert item.deleted_at is not None

    def test_restore_success(self, user):
        item = ItemService.create(sku='RESTORE-ME', name='Restore Item', unit='Pcs', user=user)
        ItemService.soft_delete(item, user=user)
        
        restored = ItemService.restore(item, user=user)
        
        assert restored.is_deleted is False
        assert restored.deleted_by is None
        assert restored.deleted_at is None
        assert restored.updated_by == user

    def test_querysets_logic(self, user):
        # 2 active, 1 deleted
        ItemService.create(sku='A1', name='Active 1', unit='Pcs', user=user)
        ItemService.create(sku='A2', name='Active 2', unit='Pcs', user=user)
        item_del = ItemService.create(sku='D1', name='Deleted 1', unit='Pcs', user=user)
        ItemService.soft_delete(item_del, user=user)
        
        active_qs = ItemService.get_active_queryset()
        active_list = ItemService.list_active()
        
        assert active_qs.count() == 2
        assert len(active_list) == 2
        
        # Verify optimized category lookup (no extra queries needed if we were iterating)
        # Note: Testing select_related presence in internal queryset state
        assert 'category' in active_qs.query.select_related
