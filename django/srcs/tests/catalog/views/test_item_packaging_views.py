import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Group
from catalog.models import Item, Category, ItemPackaging

@pytest.fixture
def test_user(db):
    user = User.objects.create_user(username="test_admin", password="password")
    group, _ = Group.objects.get_or_create(name="executive")
    user.groups.add(group)
    return user

@pytest.fixture
def auth_client(client, test_user):
    client.force_login(test_user)
    return client

@pytest.fixture
def sample_item(db, test_user):
    cat = Category.objects.create(name="Boxes", code="BOX", created_by=test_user, updated_by=test_user)
    return Item.objects.create(name="Standard Box", sku="BOX-001", category=cat, created_by=test_user, updated_by=test_user)

@pytest.fixture
def sample_packaging(sample_item, test_user):
    return ItemPackaging.objects.create(
        item=sample_item,
        name="Carton of 10",
        quantity=10,
        created_by=test_user,
        updated_by=test_user
    )

@pytest.mark.django_db
class TestItemPackagingAPI:
    def test_get_packagings_api(self, auth_client, sample_item, sample_packaging):
        url = reverse('catalog:api-item-packagings', kwargs={'item_id': sample_item.id})
        response = auth_client.get(url)
        assert response.status_code == 200
        data = response.json()
        assert 'packagings' in data
        assert len(data['packagings']) == 1
        assert data['packagings'][0]['id'] == sample_packaging.id
        assert data['packagings'][0]['name'] == 'Carton of 10'
        assert data['packagings'][0]['quantity'] == 10
        assert data['packagings'][0]['display'] == 'Carton of 10 (10 pcs)'
        assert data['base_unit'] == sample_item.unit

    def test_get_packagings_api_not_found(self, auth_client):
        url = reverse('catalog:api-item-packagings', kwargs={'item_id': 999999})
        response = auth_client.get(url)
        assert response.status_code == 404
