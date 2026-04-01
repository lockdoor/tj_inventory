import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from catalog.models import Category
from catalog.services import CategoryService

@pytest.fixture
def user(db):
    return User.objects.create_user(username='testuser', password='password123')

@pytest.mark.django_db
class TestCategoryService:
    """
    Unit tests for CategoryService business logic.
    Focuses on data integrity, hierarchical rules, and audit tracking.
    """

    def test_create_category_success(self, user):
        cat = CategoryService.create(
            name='Electronics',
            code='ELEC',
            user=user,
            note='Test electronics'
        )
        assert cat.pk is not None
        assert cat.name == 'Electronics'
        assert cat.code == 'ELEC'
        assert cat.created_by == user
        assert cat.is_deleted is False

    def test_create_category_duplicate_code_fails(self, user):
        CategoryService.create(name='First', code='DUP', user=user)
        with pytest.raises(ValidationError):
            CategoryService.create(name='Second', code='DUP', user=user)

    def test_update_category_success(self, user):
        cat = CategoryService.create(name='Old', code='OLD', user=user)
        
        updated_cat = CategoryService.update(
            cat,
            user=user,
            name='New Name',
            code='NEW'
        )
        
        assert updated_cat.name == 'New Name'
        assert updated_cat.code == 'NEW'
        assert updated_cat.updated_by == user

    def test_soft_delete_success(self, user):
        cat = CategoryService.create(name='To Delete', code='DEL', user=user)
        
        CategoryService.soft_delete(cat, user=user)
        
        cat.refresh_from_db()
        assert cat.is_deleted is True
        assert cat.deleted_by == user
        assert cat.deleted_at is not None

    def test_soft_delete_blocked_with_active_children(self, user):
        parent = CategoryService.create(name='Parent', code='P1', user=user)
        child = CategoryService.create(name='Child', code='C1', parent=parent, user=user)
        
        with pytest.raises(ValidationError) as excinfo:
            CategoryService.soft_delete(parent, user=user)
        
        assert "Cannot delete category 'Parent' because it has active children" in str(excinfo.value)
        assert "Child" in str(excinfo.value)
        
        # Verify parent still active
        parent.refresh_from_db()
        assert parent.is_deleted is False

    def test_soft_delete_allowed_with_already_deleted_children(self, user):
        parent = CategoryService.create(name='Parent', code='P1', user=user)
        child = CategoryService.create(name='Child', code='C1', parent=parent, user=user)
        
        # First, delete the child
        CategoryService.soft_delete(child, user=user)
        
        # Now, deleting parent should be allowed because child is no longer active
        CategoryService.soft_delete(parent, user=user)
        parent.refresh_from_db()
        assert parent.is_deleted is True

    def test_restore_success(self, user):
        cat = CategoryService.create(name='Deleted', code='DEL', user=user)
        CategoryService.soft_delete(cat, user=user)
        
        restored = CategoryService.restore(cat, user=user)
        
        assert restored.is_deleted is False
        assert restored.deleted_by is None
        assert restored.deleted_at is None
        assert restored.updated_by == user

    def test_restore_blocked_if_parent_is_deleted(self, user):
        parent = CategoryService.create(name='Parent', code='P1', user=user)
        child = CategoryService.create(name='Child', code='C1', parent=parent, user=user)
        
        # Soft delete both
        CategoryService.soft_delete(child, user=user)
        CategoryService.soft_delete(parent, user=user)
        
        # Restoration of child should fail while parent is still deleted
        with pytest.raises(ValidationError) as excinfo:
            CategoryService.restore(child, user=user)
            
        assert "parent 'Parent' is still in the trash" in str(excinfo.value)
        child.refresh_from_db()
        assert child.is_deleted is True

    def test_querysets_logic(self, user):
        # 2 active, 1 deleted
        CategoryService.create(name='A1', code='C1', user=user)
        CategoryService.create(name='A2', code='C2', user=user)
        cat_del = CategoryService.create(name='D1', code='CD', user=user)
        CategoryService.soft_delete(cat_del, user=user)
        
        active_list = CategoryService.list_active()
        deleted_list = CategoryService.list_deleted()
        
        assert len(active_list) == 2
        assert len(deleted_list) == 1
        assert deleted_list[0].name == 'D1'
