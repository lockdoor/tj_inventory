import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from procurement.models import Arrival, ArrivalItem
from catalog.models import Item, Category
from inventory.models import Warehouse, InventoryMovement
from partners.models import Partner

@pytest.fixture
def test_user(db):
    user = User.objects.create_user(username="authorized_user", password="password")
    perms = Permission.objects.filter(codename__in=[
        'view_arrival', 'add_arrival', 'change_arrival'
    ])
    user.user_permissions.add(*perms)
    from django.contrib.auth.models import Group
    group, _ = Group.objects.get_or_create(name='warehouse_admin')
    user.groups.add(group)
    return user

@pytest.fixture
def unauthorized_user(db):
    return User.objects.create_user(username="unauthorized_user", password="password")

@pytest.fixture
def sample_arrival(test_user, db):
    category = Category.objects.create(name="Test Category", created_by=test_user)
    item = Item.objects.create(
        sku="ARR-ITEM-01",
        name="Arrival Item",
        category=category,
        created_by=test_user
    )
    warehouse = Warehouse.objects.create(name="Main Warehouse", code="WH01", created_by=test_user)
    supplier = Partner.objects.create(name="Supplier A", code="SUPA", is_supplier=True, created_by=test_user)
    
    arrival = Arrival.objects.create(
        document_no="ARR-2026-001",
        partner=supplier,
        warehouse=warehouse,
        expected_date="2026-06-01",
        created_by=test_user,
        status=Arrival.Status.SCHEDULED
    )
    
    ArrivalItem.objects.create(
        arrival=arrival,
        item=item,
        expected_qty=Decimal("100.00"),
        created_by=test_user
    )
    return arrival

@pytest.mark.django_db
class TestArrivalReceiveActionViews:
    def test_initiate_and_cancel_receiving_views(self, client, test_user, sample_arrival):
        client.force_login(test_user)
        
        # 1. Post to initiate receiving
        initiate_url = reverse('procurement:arrival-receive', kwargs={'pk': sample_arrival.pk})
        response = client.post(initiate_url)
        sample_arrival.refresh_from_db()
        assert sample_arrival.status == Arrival.Status.RECEIVING
        
        movement = InventoryMovement.objects.get(reference_no=sample_arrival.document_no)
        assert response.status_code == 302
        assert response.url == reverse('inventory:movement-detail', kwargs={'pk': movement.pk})

        # 2. Post to cancel receiving
        cancel_url = reverse('procurement:arrival-cancel-receive', kwargs={'pk': sample_arrival.pk})
        response = client.post(cancel_url)
        sample_arrival.refresh_from_db()
        movement.refresh_from_db()
        
        assert sample_arrival.status == Arrival.Status.SCHEDULED
        assert movement.is_deleted
        assert response.status_code == 302
        assert response.url == reverse('procurement:arrival-detail', kwargs={'pk': sample_arrival.pk})

    def test_cancel_receiving_unauthorized(self, client, unauthorized_user, test_user, sample_arrival):
        # Setup arrival in receiving state
        from procurement.services import ArrivalService
        ArrivalService.initiate_receiving(sample_arrival, test_user)
        
        client.force_login(unauthorized_user)
        cancel_url = reverse('procurement:arrival-cancel-receive', kwargs={'pk': sample_arrival.pk})
        response = client.post(cancel_url)
        
        assert response.status_code == 403
        sample_arrival.refresh_from_db()
        assert sample_arrival.status == Arrival.Status.RECEIVING

    def test_initiate_receiving_non_warehouse_admin_denied(self, client, sample_arrival):
        non_wh_user = User.objects.create_user(username="non_wh_user", password="password")
        perms = Permission.objects.filter(codename__in=['view_arrival', 'change_arrival'])
        non_wh_user.user_permissions.add(*perms)
        
        client.force_login(non_wh_user)
        initiate_url = reverse('procurement:arrival-receive', kwargs={'pk': sample_arrival.pk})
        response = client.post(initiate_url)
        
        sample_arrival.refresh_from_db()
        assert sample_arrival.status == Arrival.Status.SCHEDULED
        assert response.status_code == 302
        assert response.url == reverse('procurement:arrival-detail', kwargs={'pk': sample_arrival.pk})
