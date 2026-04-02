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

@pytest.mark.django_db
class TestItemCreateView:
    """Functional tests for Item creation."""

    def test_unauthenticated_denied(self, client):
        url = reverse('catalog:item-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_sales_rep_denied(self, client, sales_user):
        # Sales reps can view but not add
        client.login(username='sales', password='password123')
        url = reverse('catalog:item-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_create_success(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        client.login(username='executive', password='password123')
        
        url = reverse('catalog:item-create')
        data = {
            'sku': 'NEW-SKU',
            'name': 'New Product',
            'category': cat.id,
            'unit': 'Pcs',
            'express_sku': 'EXP-123',
            'note': 'Fresh stock'
        }
        
        response = client.post(url, data)
        assert response.status_code == 302
        assert response.url == reverse('catalog:item-list')
        
        # Verify in DB
        del_item = Item.objects.get(sku='NEW-SKU')
        assert del_item.name == 'New Product'
        assert del_item.created_by == executive_user

    def test_duplicate_sku_error(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        Item.objects.create(sku='DUP-01', name='Existing', unit='Pcs', category=cat, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-create')
        data = {
            'sku': 'DUP-01',
            'name': 'Should Fail',
            'category': cat.id,
            'unit': 'Pcs'
        }
        
        response = client.post(url, data)
        assert response.status_code == 200
        assert 'Item with this Sku already exists' in response.content.decode()

@pytest.mark.django_db
class TestItemUpdateView:
    """Functional tests for Item updates."""

    def test_update_success(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        item = Item.objects.create(sku='SKU-1', name='Old Name', unit='Pcs', category=cat, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-update', kwargs={'pk': item.pk})
        
        # Verify title in GET request before update
        response = client.get(url)
        assert f"Update {item.name}" in response.content.decode()

        data = {
            'sku': 'SKU-1',  # Keep same SKU
            'name': 'Updated Name',
            'category': cat.id,
            'unit': 'Kg',
            'note': 'Price drop'
        }
        
        response = client.post(url, data)
        assert response.status_code == 302
        
        item.refresh_from_db()
        assert item.name == 'Updated Name'
        assert item.unit == 'Kg'
        assert item.updated_by == executive_user
