import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from catalog.models import Item, Category

@pytest.fixture(autouse=True)
def seed_groups(db):
    call_command('seed_groups')

@pytest.fixture
def executive_user(db):
    user = User.objects.create_user(username='executive', password='password123')
    if not Group.objects.filter(name='executive').exists():
        call_command('seed_groups')
    user.groups.add(Group.objects.get(name='executive'))
    return user

@pytest.fixture
def sales_user(db):
    user = User.objects.create_user(username='sales', password='password123')
    if not Group.objects.filter(name='sales_rep').exists():
        call_command('seed_groups')
    user.groups.add(Group.objects.get(name='sales_rep'))
    return user

@pytest.mark.django_db
class TestItemListView:
    """Functional tests for the Item List view."""

    def test_unauthenticated_denied(self, client):
        url = reverse('catalog:item-list')
        response = client.get(url)
        assert response.status_code == 403

    def test_sales_rep_authorized(self, client, sales_user):
        # Sales reps have 'view_item' permission
        client.login(username='sales', password='password123')
        url = reverse('catalog:item-list')
        response = client.get(url)
        assert response.status_code == 200

    def test_get_item_list_visibility(self, client, executive_user):
        cat = Category.objects.create(name='Test Cat', code='TC', created_by=executive_user)
        Item.objects.create(sku='ITEM1', name='Visible Item', unit='Pcs', category=cat, created_by=executive_user)
        Item.objects.create(sku='ITEM2', name='Hidden Item', unit='Pcs', category=cat, is_deleted=True, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-list')
        response = client.get(url)
        
        assert response.status_code == 200
        items = response.context['items']
        assert len(items) == 1
        assert items[0].sku == 'ITEM1'
        
        content = response.content.decode()
        assert 'Visible Item' in content
        assert 'Hidden Item' not in content
        assert 'Test Cat' in content
