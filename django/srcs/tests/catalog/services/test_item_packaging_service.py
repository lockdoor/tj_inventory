import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from catalog.models import Item, Category, ItemPackaging
from catalog.services import ItemService, ItemPackagingService


@pytest.fixture
def user(db):
    return User.objects.create_user(username='pkguser', password='password123')


@pytest.fixture
def category(db, user):
    return Category.objects.create(name='Packaging Cat', code='PKGC', created_by=user)


@pytest.fixture
def item(db, user, category):
    return ItemService.create(
        sku='ITEM-001',
        name='Base Item',
        unit='Pcs',
        user=user,
        category=category
    )


@pytest.fixture
def item_two(db, user, category):
    return ItemService.create(
        sku='ITEM-002',
        name='Second Item',
        unit='Pcs',
        user=user,
        category=category
    )


@pytest.mark.django_db
class TestItemPackagingService:
    """
    Unit tests for ItemPackagingService business logic.
    Focuses on name validation, quantity validation, update self-collision avoidance,
    and soft deletion behavior.
    """

    def test_create_packaging_success(self, item, user):
        pkg = ItemPackagingService.create(
            item=item,
            name=' Box ',
            quantity=12,
            barcode='  12345678  ',
            note='  Test note  ',
            user=user
        )
        assert pkg.pk is not None
        assert pkg.name == 'Box'
        assert pkg.quantity == 12
        assert pkg.barcode == '12345678'
        assert pkg.note == 'Test note'
        assert pkg.created_by == user
        assert pkg.is_deleted is False

    def test_create_duplicate_name_case_insensitive_fails(self, item, user):
        ItemPackagingService.create(item=item, name='Carton', quantity=24, user=user)
        with pytest.raises(ValueError, match="Packaging name already exists for this item"):
            ItemPackagingService.create(item=item, name='carton', quantity=12, user=user)

    def test_create_same_name_different_item_success(self, item, item_two, user):
        pkg1 = ItemPackagingService.create(item=item, name='Carton', quantity=24, user=user)
        pkg2 = ItemPackagingService.create(item=item_two, name='Carton', quantity=24, user=user)
        assert pkg1.pk != pkg2.pk
        assert pkg1.name == pkg2.name == 'Carton'

    def test_create_invalid_quantity_fails(self, item, user):
        with pytest.raises(ValueError, match="Quantity must be greater than zero"):
            ItemPackagingService.create(item=item, name='ZeroPkg', quantity=0, user=user)

        with pytest.raises(ValueError, match="Quantity must be greater than zero"):
            ItemPackagingService.create(item=item, name='NegPkg', quantity=-5, user=user)

    def test_create_empty_name_fails(self, item, user):
        with pytest.raises(ValueError, match="Packaging name cannot be empty"):
            ItemPackagingService.create(item=item, name='   ', quantity=10, user=user)

    def test_update_packaging_success_and_case_change(self, item, user):
        pkg = ItemPackagingService.create(item=item, name='dozen', quantity=12, user=user)
        
        # Updating its own name capitalization should NOT trigger self-collision
        updated = ItemPackagingService.update(pkg, user=user, name='Dozen', quantity=12)
        assert updated.name == 'Dozen'

        # Updating other fields while keeping name should work perfectly
        updated2 = ItemPackagingService.update(pkg, user=user, quantity=15, note='New note')
        assert updated2.quantity == 15
        assert updated2.note == 'New note'

    def test_update_duplicate_name_collision_fails(self, item, user):
        pkg1 = ItemPackagingService.create(item=item, name='Box', quantity=10, user=user)
        pkg2 = ItemPackagingService.create(item=item, name='Carton', quantity=50, user=user)

        with pytest.raises(ValueError, match="Packaging name already exists for this item"):
            ItemPackagingService.update(pkg1, user=user, name='carton')

    def test_soft_delete_and_reuse_name(self, item, user):
        pkg = ItemPackagingService.create(item=item, name='Pallet', quantity=100, user=user)
        
        ItemPackagingService.delete(pkg, user=user)
        pkg.refresh_from_db()
        assert pkg.is_deleted is True

        # Once soft-deleted, creating another packaging with the same name is allowed
        new_pkg = ItemPackagingService.create(item=item, name='Pallet', quantity=120, user=user)
        assert new_pkg.pk != pkg.pk
        assert new_pkg.is_deleted is False

    def test_get_active_for_item_ordering(self, item, user):
        pkg_large = ItemPackagingService.create(item=item, name='Large', quantity=100, user=user)
        pkg_small = ItemPackagingService.create(item=item, name='Small', quantity=5, user=user)
        pkg_med = ItemPackagingService.create(item=item, name='Medium', quantity=25, user=user)
        pkg_deleted = ItemPackagingService.create(item=item, name='Del', quantity=10, user=user)
        ItemPackagingService.delete(pkg_deleted, user=user)

        active = list(ItemPackagingService.get_active_for_item(item))
        assert len(active) == 3
        assert active == [pkg_small, pkg_med, pkg_large]
