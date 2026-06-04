import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User, Permission, Group
from django.core.exceptions import PermissionDenied
from procurement.models import Arrival, ArrivalItem, ArrivalReservation
from catalog.models import Item, Category
from inventory.models import Warehouse
from partners.models import Partner
from procurement.services import ArrivalReservationService


@pytest.fixture
def base_data(db):
    """
    Sets up common base catalog and logistics models.
    """
    admin_user = User.objects.create_superuser(username="admin", password="password")
    category = Category.objects.create(name="Beverages", created_by=admin_user)
    
    item_a = Item.objects.create(
        sku="SKU-A",
        name="Min Min Candy Watermelon",
        category=category,
        created_by=admin_user
    )
    item_b = Item.objects.create(
        sku="SKU-B",
        name="Coke Zero",
        category=category,
        created_by=admin_user
    )
    
    warehouse_a = Warehouse.objects.create(name="Main Warehouse", code="WH-MAIN", status="active", created_by=admin_user)
    warehouse_b = Warehouse.objects.create(name="Second Warehouse", code="WH-SEC", status="active", created_by=admin_user)
    
    supplier = Partner.objects.create(name="TJ Global Ltd", code="TJGB", is_supplier=True, created_by=admin_user)
    
    # Create Arrival schedules
    arrival_1 = Arrival.objects.create(
        document_no="ARR-2026-001",
        partner=supplier,
        warehouse=warehouse_a,
        expected_date="2026-08-12",
        status=Arrival.Status.SCHEDULED,
        created_by=admin_user
    )
    arrival_2 = Arrival.objects.create(
        document_no="ARR-2026-002",
        partner=supplier,
        warehouse=warehouse_b,
        expected_date="2026-08-15",
        status=Arrival.Status.RECEIVING,
        created_by=admin_user
    )
    
    arrival_item_1 = ArrivalItem.objects.create(
        arrival=arrival_1,
        item=item_a,
        expected_qty=Decimal("100.00"),
        received_qty=Decimal("0.00")
    )
    arrival_item_2 = ArrivalItem.objects.create(
        arrival=arrival_2,
        item=item_b,
        expected_qty=Decimal("50.00"),
        received_qty=Decimal("0.00")
    )
    
    return {
        "item_a": item_a,
        "item_b": item_b,
        "warehouse_a": warehouse_a,
        "warehouse_b": warehouse_b,
        "arrival_item_1": arrival_item_1,
        "arrival_item_2": arrival_item_2,
    }


@pytest.fixture
def creator_user(db):
    user = User.objects.create_user(username="creator_user", password="password")
    perm = Permission.objects.get(codename="view_arrival")
    user.user_permissions.add(perm)
    return user


@pytest.fixture
def non_creator_user(db):
    user = User.objects.create_user(username="non_creator_user", password="password")
    perm = Permission.objects.get(codename="view_arrival")
    user.user_permissions.add(perm)
    return user


@pytest.fixture
def executive_user(db):
    user = User.objects.create_user(username="executive_user", password="password")
    perm = Permission.objects.get(codename="view_arrival")
    user.user_permissions.add(perm)
    group, _ = Group.objects.get_or_create(name="executive")
    user.groups.add(group)
    return user


@pytest.fixture
def unauthorized_user(db):
    return User.objects.create_user(username="unauthorized_user", password="password")


@pytest.mark.django_db
class TestArrivalReservationAccessControl:
    """
    Test access controls and login/permission gates.
    """
    def test_unauthenticated_redirect(self, client, base_data):
        # List view
        assert client.get(reverse('procurement:arrival-reservation-list')).status_code == 302
        # Create view
        assert client.get(reverse('procurement:arrival-reservation-create')).status_code == 302
        
    def test_unauthorized_user_forbidden(self, client, unauthorized_user, base_data):
        client.force_login(unauthorized_user)
        
        # List view -> 403
        assert client.get(reverse('procurement:arrival-reservation-list')).status_code == 403
        # Create view -> 403
        assert client.get(reverse('procurement:arrival-reservation-create')).status_code == 403


@pytest.mark.django_db
class TestArrivalReservationListViews:
    """
    Test list view, search filtering, and pagination.
    """
    def test_list_and_search_q(self, client, creator_user, base_data):
        client.force_login(creator_user)
        
        # Create arrival reservations
        res_1 = ArrivalReservationService.reserve_future(
            arrival_item=base_data["arrival_item_1"],
            quantity=Decimal("30.00"),
            reference_no="SO-9991",
            reference_type=ArrivalReservation.ReferenceType.SALES_ORDER,
            note="Pre-sale candy to client",
            created_by=creator_user
        )
        res_2 = ArrivalReservationService.reserve_future(
            arrival_item=base_data["arrival_item_2"],
            quantity=Decimal("15.00"),
            reference_no="PR-0005",
            reference_type=ArrivalReservation.ReferenceType.PRODUCTION,
            note="Coke zero for testing",
            created_by=creator_user
        )
        
        # 1. Fetch complete list
        url = reverse('procurement:arrival-reservation-list')
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context['reservations']) == 2
        
        # 2. Search by SKU
        response = client.get(f"{url}?q=SKU-A")
        assert response.status_code == 200
        assert len(response.context['reservations']) == 1
        assert response.context['reservations'][0].pk == res_1.pk
        
        # 3. Search by Ref No
        response = client.get(f"{url}?q=PR-0005")
        assert response.status_code == 200
        assert len(response.context['reservations']) == 1
        assert response.context['reservations'][0].pk == res_2.pk
        
        # 4. Search by Note
        response = client.get(f"{url}?q=candy")
        assert response.status_code == 200
        assert len(response.context['reservations']) == 1
        assert response.context['reservations'][0].pk == res_1.pk


@pytest.mark.django_db
class TestArrivalReservationCreateViews:
    """
    Test creation views, validation errors, and remaining capacity calculations.
    """
    def test_get_create_form(self, client, creator_user):
        client.force_login(creator_user)
        response = client.get(reverse('procurement:arrival-reservation-create'))
        assert response.status_code == 200
        assert 'form' in response.context
        
    def test_create_reservation_success(self, client, creator_user, base_data):
        client.force_login(creator_user)
        
        post_data = {
            'warehouse': base_data["warehouse_a"].name,
            'arrival_item': base_data["arrival_item_1"].pk,
            'quantity': '40.00',
            'reference_type': ArrivalReservation.ReferenceType.SALES_ORDER,
            'reference_no': 'SO-X-101',
            'note': 'Urgent customer hold'
        }
        
        response = client.post(reverse('procurement:arrival-reservation-create'), data=post_data)
        assert response.status_code == 302
        assert response.url == reverse('procurement:arrival-reservation-list')
        
        # Verify in DB
        res = ArrivalReservation.objects.get(reference_no='SO-X-101')
        assert res.quantity == Decimal("40.00")
        assert res.created_by == creator_user
        
        # Verify reserved_qty is synced
        base_data["arrival_item_1"].refresh_from_db()
        assert base_data["arrival_item_1"].reserved_qty == Decimal("40.00")
        
    def test_create_reservation_quantity_less_than_zero(self, client, creator_user, base_data):
        client.force_login(creator_user)
        
        post_data = {
            'warehouse': base_data["warehouse_a"].name,
            'arrival_item': base_data["arrival_item_1"].pk,
            'quantity': '-5.00',
            'reference_type': ArrivalReservation.ReferenceType.INTERNAL,
            'reference_no': 'REF-ERR',
            'note': ''
        }
        
        response = client.post(reverse('procurement:arrival-reservation-create'), data=post_data)
        assert response.status_code == 200 # Re-renders page
        assert 'quantity' in response.context['form'].errors
        assert not ArrivalReservation.objects.filter(reference_no='REF-ERR').exists()

    def test_create_reservation_insufficient_expected_qty(self, client, creator_user, base_data):
        client.force_login(creator_user)
        
        # First reservation uses 80.00 units out of 100.00 available on arrival_item_1
        ArrivalReservationService.reserve_future(
            arrival_item=base_data["arrival_item_1"],
            quantity=Decimal("80.00"),
            reference_no="SO-FIRST",
            created_by=creator_user
        )
        
        # Second reservation tries to hold 30.00 units (remaining is only 20.00)
        post_data = {
            'warehouse': base_data["warehouse_a"].name,
            'arrival_item': base_data["arrival_item_1"].pk,
            'quantity': '30.00',
            'reference_type': ArrivalReservation.ReferenceType.SALES_ORDER,
            'reference_no': 'SO-SECOND-FAIL',
            'note': ''
        }
        
        response = client.post(reverse('procurement:arrival-reservation-create'), data=post_data)
        assert response.status_code == 200
        assert 'quantity' in response.context['form'].errors
        assert not ArrivalReservation.objects.filter(reference_no='SO-SECOND-FAIL').exists()

    def test_create_reservation_excludes_soft_deleted_arrivals(self, client, creator_user, base_data):
        client.force_login(creator_user)
        
        # Soft delete arrival_1
        arrival_1 = base_data["arrival_item_1"].arrival
        arrival_1.delete()
        assert arrival_1.is_deleted is True
        
        response = client.get(reverse('procurement:arrival-reservation-create'))
        assert response.status_code == 200
        
        # Verify the queryset of arrival_item excludes arrival_item_1 and includes arrival_item_2
        queryset = response.context['form'].fields['arrival_item'].queryset
        assert base_data["arrival_item_2"] in queryset
        assert base_data["arrival_item_1"] not in queryset


@pytest.mark.django_db
class TestArrivalReservationDetailView:
    """
    Test viewing detailed expected arrival reservation metrics.
    """
    def test_detail_view(self, client, creator_user, base_data):
        client.force_login(creator_user)
        
        res = ArrivalReservationService.reserve_future(
            arrival_item=base_data["arrival_item_1"],
            quantity=Decimal("10.00"),
            reference_no="SO-DETAIL",
            created_by=creator_user
        )
        
        url = reverse('procurement:arrival-reservation-detail', kwargs={'pk': res.pk})
        response = client.get(url)
        
        assert response.status_code == 200
        assert response.context['reservation'].pk == res.pk
        assert response.context['reservation'].arrival_item.item.sku == "SKU-A"


@pytest.mark.django_db
class TestArrivalReservationReleaseView:
    """
    Test secure release authorization controls (Creator/Executive/Superuser gate).
    """
    @pytest.fixture
    def active_res(self, creator_user, base_data):
        return ArrivalReservationService.reserve_future(
            arrival_item=base_data["arrival_item_1"],
            quantity=Decimal("50.00"),
            reference_no="SO-LOCK-ME",
            created_by=creator_user
        )

    def test_release_by_creator_succeeds(self, client, creator_user, active_res, base_data):
        client.force_login(creator_user)
        
        url = reverse('procurement:arrival-reservation-release', kwargs={'pk': active_res.pk})
        response = client.post(url)
        
        assert response.status_code == 302
        assert response.url == reverse('procurement:arrival-reservation-list')
        
        # Verify in DB (should be deleted)
        assert not ArrivalReservation.objects.filter(pk=active_res.pk, is_deleted=False).exists()
        
        # Verify arrival_item reserved_qty synced back to 0.00
        base_data["arrival_item_1"].refresh_from_db()
        assert base_data["arrival_item_1"].reserved_qty == Decimal("0.00")

    def test_release_by_executive_succeeds(self, client, executive_user, active_res, base_data):
        client.force_login(executive_user)
        
        url = reverse('procurement:arrival-reservation-release', kwargs={'pk': active_res.pk})
        response = client.post(url)
        
        assert response.status_code == 302
        assert response.url == reverse('procurement:arrival-reservation-list')
        assert not ArrivalReservation.objects.filter(pk=active_res.pk, is_deleted=False).exists()

    def test_release_by_superuser_succeeds(self, client, active_res, base_data):
        superuser = User.objects.create_superuser(username="super", password="password")
        client.force_login(superuser)
        
        url = reverse('procurement:arrival-reservation-release', kwargs={'pk': active_res.pk})
        response = client.post(url)
        
        assert response.status_code == 302
        assert response.url == reverse('procurement:arrival-reservation-list')
        assert not ArrivalReservation.objects.filter(pk=active_res.pk, is_deleted=False).exists()

    def test_release_by_non_creator_non_executive_fails(self, client, non_creator_user, active_res, base_data):
        client.force_login(non_creator_user)
        
        url = reverse('procurement:arrival-reservation-release', kwargs={'pk': active_res.pk})
        
        # In Django, raise_exception=True throws PermissionDenied, which standard Client converts to 403 status code.
        response = client.post(url)
        assert response.status_code == 403
        
        # Verify reservation is still intact
        assert ArrivalReservation.objects.filter(pk=active_res.pk, is_deleted=False).exists()
        
        base_data["arrival_item_1"].refresh_from_db()
        assert base_data["arrival_item_1"].reserved_qty == Decimal("50.00")
