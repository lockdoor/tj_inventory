import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from catalog.services import CategoryService, ItemService

@pytest.fixture
def user(db):
    user = User.objects.create_user(username='staff', password='password123')
    # Grant view_category permission as it's required for the dashboard
    perm = Permission.objects.get(codename='view_category')
    user.user_permissions.add(perm)
    return user

@pytest.mark.django_db
class TestCatalogOverviewView:
    def test_unauthenticated_denied(self, client):
        url = reverse('catalog:catalog-overview')
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login

    def test_authorized_access(self, client, user):
        client.login(username='staff', password='password123')
        url = reverse('catalog:catalog-overview')
        
        # Seed some data to check counts
        CategoryService.create(name='Cat 1', code='C1', user=user)
        ItemService.create(sku='SKU1', name='Item 1', unit='Pcs', user=user)
        
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'category_count' in response.context
        assert 'item_count' in response.context
        assert response.context['category_count'] == 1
        assert response.context['item_count'] == 1
        assert b'Catalog Overview' in response.content

    def test_missing_permission_denied(self, client):
        # Create user without view_category permission
        u = User.objects.create_user(username='no-perm', password='password123')
        client.login(username='no-perm', password='password123')
        
        url = reverse('catalog:catalog-overview')
        response = client.get(url)
        
        assert response.status_code == 403  # Forbidden
