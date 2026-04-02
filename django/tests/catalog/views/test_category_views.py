import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from catalog.models import Category

@pytest.fixture(autouse=True)
def seed_groups(db):
    """Seed groups and permissions before each test."""
    call_command('seed_groups')

@pytest.fixture
def executive_user(db):
    user = User.objects.create_user(username='executive', password='password123')
    user.groups.add(Group.objects.get(name='executive'))
    return user

@pytest.fixture
def sales_user(db):
    user = User.objects.create_user(username='sales', password='password123')
    user.groups.add(Group.objects.get(name='sales_rep'))
    return user

@pytest.fixture
def public_user(db):
    return User.objects.create_user(username='public', password='password123')

@pytest.mark.django_db
class TestCategoryPermissions:
    """Tests for view-level permission gating."""
    
    def test_unauthenticated_denied(self, client):
        url = reverse('catalog:category-create')
        response = client.get(url)
        # We set raise_exception = True, so even unauthenticated gets 403
        assert response.status_code == 403

    def test_sales_rep_denied(self, client, sales_user):
        client.login(username='sales', password='password123')
        url = reverse('catalog:category-create')
        response = client.get(url)
        # We set raise_exception = True, so it should be 403 Forbidden
        assert response.status_code == 403

    def test_public_user_denied(self, client, public_user):
        client.login(username='public', password='password123')
        url = reverse('catalog:category-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_executive_authorized(self, client, executive_user):
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-list')
        response = client.get(url)
        assert response.status_code == 200

@pytest.mark.django_db
class TestCategoryListView:
    """Functional tests for the Category List view."""
    
    def test_unauthenticated_denied(self, client):
        url = reverse('catalog:category-list')
        response = client.get(url)
        # Perm required mixin with raise_exception=True throws 403
        assert response.status_code == 403

    def test_get_category_list(self, client, sales_user):
        # Create some categories
        Category.objects.create(name='Electronics', code='ELEC', created_by=sales_user)
        Category.objects.create(name='Furniture', code='FURN', created_by=sales_user)
        # Soft deleted should be hidden
        Category.objects.create(name='Hidden', code='HIDE', is_deleted=True, created_by=sales_user)
        
        client.login(username='sales', password='password123')
        url = reverse('catalog:category-list')
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'categories' in response.context
        categories = response.context['categories']
        assert len(categories) == 2
        assert any(c.code == 'ELEC' for c in categories)
        assert not any(c.code == 'HIDE' for c in categories)

    def test_action_buttons_permission_gating(self, client, sales_user, executive_user):
        # Create a category to test button visibility
        Category.objects.create(name='Test Category', code='TEST', created_by=executive_user)
        
        # Sales rep should NOT see Add/Edit/Delete
        client.login(username='sales', password='password123')
        url = reverse('catalog:category-list')
        response = client.get(url)
        content = response.content.decode()
        assert 'Add Category' not in content
        assert 'title="Update"' not in content # Buttons in template use title for tooltips

        # Executive SHOULD see them
        client.login(username='executive', password='password123')
        response = client.get(url)
        content = response.content.decode()
        assert 'Add Category' in content
        assert 'Add Category' in content
        assert 'title="Update"' in content

@pytest.mark.django_db
class TestCategoryDetailView:
    """Functional tests for the Category Detail view."""
    
    def test_unauthenticated_denied(self, client, executive_user):
        cat = Category.objects.create(name='Test', code='T1', created_by=executive_user)
        url = reverse('catalog:category-detail', kwargs={'code': cat.code})
        response = client.get(url)
        assert response.status_code == 403

    def test_get_category_detail(self, client, sales_user):
        parent = Category.objects.create(name='Parent', code='P1', created_by=sales_user)
        child = Category.objects.create(name='Child', code='C1', parent=parent, created_by=sales_user)
        
        client.login(username='sales', password='password123')
        url = reverse('catalog:category-detail', kwargs={'code': child.code})
        response = client.get(url)
        
        assert response.status_code == 200
        assert response.context['category'] == child
        content = response.content.decode()
        assert 'Parent' in content
        assert 'Child' in content

    def test_get_deleted_category_404(self, client, executive_user):
        cat = Category.objects.create(name='Deleted', code='DEL', is_deleted=True, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-detail', kwargs={'code': cat.code})
        response = client.get(url)
        
        # DetailView should return 404 if queryset filters out deleted
        assert response.status_code == 404

@pytest.mark.django_db
class TestCategoryUpdateView:
    """Functional tests for the Category Update view."""

    def test_unauthenticated_denied(self, client, executive_user):
        cat = Category.objects.create(name='Test', code='T1', created_by=executive_user)
        url = reverse('catalog:category-update', kwargs={'code': cat.code})
        response = client.get(url)
        assert response.status_code == 403

    def test_sales_rep_denied(self, client, sales_user):
        cat = Category.objects.create(name='Test', code='T1', created_by=sales_user)
        client.login(username='sales', password='password123')
        url = reverse('catalog:category-update', kwargs={'code': cat.code})
        response = client.get(url)
        assert response.status_code == 403

    def test_executive_update_success(self, client, executive_user):
        cat = Category.objects.create(name='Old Name', code='OLD', created_by=executive_user)
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-update', kwargs={'code': cat.code})
        
        data = {
            'name': 'New Name',
            'code': 'NEW',
            'parent': '',
            'note': 'Updated notes',
            'status': 'active'
        }
        response = client.post(url, data)
        
        # Should redirect to detail view
        assert response.status_code == 302
        cat.refresh_from_db()
        assert cat.name == 'New Name'
        assert cat.code == 'NEW'
        assert cat.updated_by == executive_user

    def test_update_duplicate_code_fails(self, client, executive_user):
        Category.objects.create(name='Other', code='BUSY', created_by=executive_user)
        cat = Category.objects.create(name='Mine', code='MINE', created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-update', kwargs={'code': cat.code})
        
        data = {'name': 'Mine', 'code': 'BUSY', 'parent': '', 'note': ''}
        response = client.post(url, data)
        
        assert response.status_code == 200 # Returns to form with errors
        assert 'code' in response.context['form'].errors

@pytest.mark.django_db
class TestCategoryDeleteView:
    """Functional tests for the Category Delete view."""

    def test_unauthenticated_denied(self, client, executive_user):
        cat = Category.objects.create(name='Test', code='T1', created_by=executive_user)
        url = reverse('catalog:category-delete', kwargs={'code': cat.code})
        response = client.get(url)
        assert response.status_code == 403

    def test_executive_delete_success(self, client, executive_user):
        cat = Category.objects.create(name='To Delete', code='DEL', created_by=executive_user)
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-delete', kwargs={'code': cat.code})
        
        # GET should show confirmation
        response = client.get(url)
        assert response.status_code == 200
        assert 'Delete Category?' in response.content.decode()

        # POST should execute soft-delete
        response = client.post(url)
        assert response.status_code == 302
        cat.refresh_from_db()
        assert cat.is_deleted is True
        assert cat.deleted_by == executive_user

    def test_delete_blocked_by_children(self, client, executive_user):
        parent = Category.objects.create(name='Parent', code='P1', created_by=executive_user)
        child = Category.objects.create(name='Child', code='C1', parent=parent, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-delete', kwargs={'code': parent.code})
        
        # GET should show warning
        response = client.get(url)
        assert 'Warning: This category has children!' in response.content.decode()

        # POST should fail (re-render with error)
        response = client.post(url)
        assert response.status_code == 200
        messages = [m.message for m in response.context['messages']]
        assert "Cannot delete category" in messages[0]
        
        # Verify it still exists in active queryset
        assert Category.objects.filter(pk=parent.pk, is_deleted=False).exists()
        
    def test_sales_rep_denied(self, client, sales_user):
        cat = Category.objects.create(name='Test', code='T1', created_by=sales_user)
        client.login(username='sales', password='password123')
        url = reverse('catalog:category-delete', kwargs={'code': cat.code})
        response = client.post(url)
        assert response.status_code == 403

@pytest.mark.django_db
class TestCategoryTrashView:
    """Functional tests for the Category Trash & Restore functionality."""

    def test_executive_view_trash(self, client, executive_user):
        Category.objects.create(name='Active', code='ACT', created_by=executive_user)
        cat = Category.objects.create(name='Deleted', code='DEL', created_by=executive_user)
        cat.delete(user=executive_user) # Use soft-delete method to set deleted_by/at
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-trash')
        response = client.get(url)
        
        assert response.status_code == 200
        content = response.content.decode()
        assert 'Deleted' in content
        assert 'Active' not in content

    def test_executive_restore_success(self, client, executive_user):
        cat = Category.objects.create(name='To Restore', code='RES', is_deleted=True, created_by=executive_user)
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-restore', kwargs={'code': cat.code})
        
        response = client.post(url)
        assert response.status_code == 302 # Redirect to list
        cat.refresh_from_db()
        assert cat.is_deleted is False
        assert cat.updated_by == executive_user

    def test_restore_blocked_by_deleted_parent(self, client, executive_user):
        parent = Category.objects.create(name='Parent', code='P1', is_deleted=True, created_by=executive_user)
        child = Category.objects.create(name='Child', code='C1', parent=parent, is_deleted=True, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-restore', kwargs={'code': child.code})
        
        response = client.post(url, follow=True) # Follow redirect to see messages
        assert response.status_code == 200 
        messages = [m.message for m in response.context['messages']]
        assert "parent 'Parent' is still in the trash" in messages[0]
        
        # Verify it is still deleted
        child.refresh_from_db()
        assert child.is_deleted is True

    def test_sales_rep_denied_trash(self, client, sales_user, executive_user):
        Category.objects.create(name='Deleted', code='DEL', is_deleted=True, created_by=executive_user)
        client.login(username='sales', password='password123')
        
        # Check trash list access
        url_list = reverse('catalog:category-trash')
        assert client.get(url_list).status_code == 403
        
        # Check restore action access
        cat = Category.objects.get(code='DEL')
        url_restore = reverse('catalog:category-restore', kwargs={'code': cat.code})
        assert client.post(url_restore).status_code == 403

@pytest.mark.django_db
class TestCategoryCreateView:
    """Functional tests for the Create view logic with an authorized user."""
    
    def test_get_category_create_view(self, client, executive_user):
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-create')
        response = client.get(url)
        assert response.status_code == 200
        assert 'catalog/category_form.html' in [t.name for t in response.templates]

    def test_post_category_create_success(self, client, executive_user):
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-create')
        data = {
            'name': 'New Category',
            'code': 'CAT-001',
            'parent': '',
            'note': 'Test note',
            'status': 'active'
        }
        response = client.post(url, data)
        assert response.status_code == 302 # Redirect on success
        assert Category.objects.filter(code='CAT-001').exists()
        
        # Verify success message and redirect
        response = client.get(url, follow=True)
        messages = [m.message for m in response.context['messages']]
        assert "Category 'New Category' created successfully!" in messages

    def test_post_category_create_duplicate_code(self, client, executive_user):
        # Create initial category
        Category.objects.create(name='Original', code='DUP-001', created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:category-create')
        data = {
            'name': 'Duplicate',
            'code': 'DUP-001',
            'parent': '',
            'note': 'Should fail'
        }
        response = client.post(url, data)
        assert response.status_code == 200
        assert 'code' in response.context['form'].errors
        assert 'category with this code already exists' in response.context['form'].errors['code'][0].lower()
