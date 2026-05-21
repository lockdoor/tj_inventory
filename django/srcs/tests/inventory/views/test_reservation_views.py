import pytest
from decimal import Decimal
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from inventory.models import Stock, Warehouse, StockReservation
from catalog.models import Item

@pytest.fixture
def authorized_user(db):
    user = User.objects.create_user(username='auth_user', password='password123')
    perms = Permission.objects.filter(codename__in=['view_stock'])
    user.user_permissions.add(*perms)
    return user

@pytest.fixture
def unauthorized_user(db):
    return User.objects.create_user(username='unauth_user', password='password123')

@pytest.fixture
def reservation_setup(db, authorized_user):
    # Setup Warehouse
    wh = Warehouse.objects.create(name='Main WH', code='MWH', created_by=authorized_user)
    
    # Setup Items
    item1 = Item.objects.create(name='Premium Widgets', sku='WGT-001', created_by=authorized_user)
    item2 = Item.objects.create(name='Super Gadgets', sku='GDT-999', created_by=authorized_user)
    
    # Setup Stock Lots
    stock1 = Stock.objects.create(
        warehouse=wh,
        item=item1,
        lot_number='LOT-WGT-A',
        balance=100.00,
        created_by=authorized_user
    )
    stock2 = Stock.objects.create(
        warehouse=wh,
        item=item2,
        lot_number='LOT-GDT-B',
        balance=50.00,
        created_by=authorized_user
    )
    
    # Setup Reservations
    res1 = StockReservation.objects.create(
        stock=stock1,
        quantity=Decimal('25.50'),
        reference_type=StockReservation.ReferenceType.SALES_ORDER,
        reference_no='SO-2026-001',
        note='Reserve for critical customer order',
        created_by=authorized_user
    )
    
    res2 = StockReservation.objects.create(
        stock=stock2,
        quantity=Decimal('10.00'),
        reference_type=StockReservation.ReferenceType.HOLD,
        reference_no='QLD-HOLD-99',
        note='Quality team inspection block',
        created_by=authorized_user
    )

    from inventory.services import ReservationService
    ReservationService._sync_stock_reserved_qty(stock1)
    ReservationService._sync_stock_reserved_qty(stock2)
    
    return {
        'wh': wh,
        'item1': item1,
        'item2': item2,
        'stock1': stock1,
        'stock2': stock2,
        'res1': res1,
        'res2': res2
    }

@pytest.mark.django_db
class TestStockReservationListView:

    def test_unauthenticated_forbidden(self, client):
        url = reverse('inventory:reservation-list')
        response = client.get(url)
        assert response.status_code == 403

    def test_unauthorized_user_forbidden(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('inventory:reservation-list')
        response = client.get(url)
        assert response.status_code == 403

    def test_authorized_user_success(self, client, authorized_user, reservation_setup):
        client.force_login(authorized_user)
        url = reverse('inventory:reservation-list')
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'reservations' in response.context
        assert len(response.context['reservations']) == 2
        
        # Verify specific content is rendered
        content = response.content.decode('utf-8')
        assert 'SO-2026-001' in content
        assert 'QLD-HOLD-99' in content
        assert 'Premium Widgets' in content
        assert 'WGT-001' in content
        assert 'LOT-WGT-A' in content
        assert 'LOT-GDT-B' in content
        assert '25.50' in content
        assert '10.00' in content

    def test_search_filtering(self, client, authorized_user, reservation_setup):
        client.force_login(authorized_user)
        url = reverse('inventory:reservation-list')
        
        # Search by reference number
        response = client.get(url, {'q': 'SO-2026-001'})
        assert response.status_code == 200
        reservations = response.context['reservations']
        assert len(reservations) == 1
        assert reservations[0].reference_no == 'SO-2026-001'
        
        # Search by SKU
        response = client.get(url, {'q': 'GDT-999'})
        assert response.status_code == 200
        reservations = response.context['reservations']
        assert len(reservations) == 1
        assert reservations[0].reference_no == 'QLD-HOLD-99'
        
        # Search by lot number
        response = client.get(url, {'q': 'LOT-WGT-A'})
        assert response.status_code == 200
        reservations = response.context['reservations']
        assert len(reservations) == 1
        assert reservations[0].reference_no == 'SO-2026-001'

        # Search with non-matching term
        response = client.get(url, {'q': 'NONEXISTENT'})
        assert response.status_code == 200
        reservations = response.context['reservations']
        assert len(reservations) == 0


@pytest.mark.django_db
class TestStockReservationCreateView:

    def test_unauthenticated_forbidden(self, client):
        url = reverse('inventory:reservation-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_unauthorized_user_forbidden(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('inventory:reservation-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_authorized_user_get_form_success(self, client, authorized_user):
        client.force_login(authorized_user)
        url = reverse('inventory:reservation-create')
        response = client.get(url)
        assert response.status_code == 200
        assert 'form' in response.context

    def test_authorized_user_post_valid_data_success(self, client, authorized_user, reservation_setup):
        client.force_login(authorized_user)
        url = reverse('inventory:reservation-create')
        
        # stock1 has balance 100.00, res1 has quantity 25.50. Available: 74.50.
        # Let's reserve another 30.00
        stock1 = reservation_setup['stock1']
        data = {
            'stock': stock1.pk,
            'quantity': '30.00',
            'reference_type': StockReservation.ReferenceType.PRODUCTION,
            'reference_no': 'PROD-HOLD-2026',
            'note': 'Production lock test'
        }
        
        response = client.post(url, data)
        assert response.status_code == 302
        assert response.url == reverse('inventory:reservation-list')
        
        # Verify db insertion
        assert StockReservation.objects.filter(reference_no='PROD-HOLD-2026').exists()
        
        # Verify stock synced
        stock1.refresh_from_db()
        assert stock1.reserved_qty == Decimal('55.50')  # 25.50 + 30.00

    def test_authorized_user_post_invalid_quantity_fails(self, client, authorized_user, reservation_setup):
        client.force_login(authorized_user)
        url = reverse('inventory:reservation-create')
        stock1 = reservation_setup['stock1']
        
        # Case A: Exceeding available qty (available is 74.50, request 80.00)
        data = {
            'stock': stock1.pk,
            'quantity': '80.00',
            'reference_type': StockReservation.ReferenceType.HOLD,
            'reference_no': 'OVERALLOC',
            'note': 'Should fail'
        }
        response = client.post(url, data)
        assert response.status_code == 200
        form = response.context['form']
        assert not form.is_valid()
        assert 'quantity' in form.errors
        assert 'Insufficient available quantity' in form.errors['quantity'][0]

        # Case B: Quantity <= 0
        data['quantity'] = '0.00'
        response = client.post(url, data)
        assert response.status_code == 200
        form = response.context['form']
        assert not form.is_valid()
        assert 'quantity' in form.errors
        assert 'Quantity must be greater than zero.' in form.errors['quantity'][0]


@pytest.mark.django_db
class TestStockReservationDetailView:

    def test_unauthenticated_forbidden(self, client, reservation_setup):
        res1 = reservation_setup['res1']
        url = reverse('inventory:reservation-detail', kwargs={'pk': res1.pk})
        response = client.get(url)
        assert response.status_code == 403

    def test_unauthorized_user_forbidden(self, client, unauthorized_user, reservation_setup):
        client.force_login(unauthorized_user)
        res1 = reservation_setup['res1']
        url = reverse('inventory:reservation-detail', kwargs={'pk': res1.pk})
        response = client.get(url)
        assert response.status_code == 403

    def test_authorized_user_success(self, client, authorized_user, reservation_setup):
        client.force_login(authorized_user)
        res1 = reservation_setup['res1']
        url = reverse('inventory:reservation-detail', kwargs={'pk': res1.pk})
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'reservation' in response.context
        assert response.context['reservation'].pk == res1.pk
        
        # Verify rendering content
        content = response.content.decode('utf-8')
        assert 'SO-2026-001' in content
        assert 'Reserve for critical customer order' in content
        assert 'Premium Widgets' in content
        assert 'LOT-WGT-A' in content

    def test_nonexistent_returns_404(self, client, authorized_user):
        client.force_login(authorized_user)
        url = reverse('inventory:reservation-detail', kwargs={'pk': 9999})
        response = client.get(url)
        assert response.status_code == 404


@pytest.mark.django_db
class TestStockReservationReleaseView:

    def test_unauthenticated_forbidden(self, client, reservation_setup):
        res1 = reservation_setup['res1']
        url = reverse('inventory:reservation-release', kwargs={'pk': res1.pk})
        response = client.post(url)
        assert response.status_code == 403

    def test_unauthorized_user_forbidden(self, client, unauthorized_user, reservation_setup):
        client.force_login(unauthorized_user)
        res1 = reservation_setup['res1']
        url = reverse('inventory:reservation-release', kwargs={'pk': res1.pk})
        response = client.post(url)
        assert response.status_code == 403

    def test_creator_can_release_success(self, client, authorized_user, reservation_setup):
        client.force_login(authorized_user)
        res1 = reservation_setup['res1']
        stock1 = reservation_setup['stock1']
        url = reverse('inventory:reservation-release', kwargs={'pk': res1.pk})
        
        # Verify initial reserved qty
        stock1.refresh_from_db()
        assert stock1.reserved_qty == Decimal('25.50')
        
        response = client.post(url)
        assert response.status_code == 302
        assert response.url == reverse('inventory:reservation-list')
        
        # Verify db deletion
        assert not StockReservation.objects.filter(pk=res1.pk).exists()
        
        # Verify stock synced back to 0
        stock1.refresh_from_db()
        assert stock1.reserved_qty == Decimal('0.00')

    def test_non_creator_cannot_release_forbidden(self, client, db, reservation_setup):
        # Create another authorized user (has view_stock permission) who did not create the reservation
        other_user = User.objects.create_user(username='other_user', password='password123')
        perms = Permission.objects.filter(codename__in=['view_stock'])
        other_user.user_permissions.add(*perms)
        
        client.force_login(other_user)
        res1 = reservation_setup['res1']  # created_by is authorized_user
        
        url = reverse('inventory:reservation-release', kwargs={'pk': res1.pk})
        response = client.post(url)
        assert response.status_code == 403  # PermissionDenied raises 403

    def test_executive_can_release_other_user_reservation_success(self, client, db, reservation_setup):
        from django.contrib.auth.models import Group
        # Create an executive user
        exec_user = User.objects.create_user(username='exec_user', password='password123')
        perms = Permission.objects.filter(codename__in=['view_stock'])
        exec_user.user_permissions.add(*perms)
        exec_group, _ = Group.objects.get_or_create(name='executive')
        exec_user.groups.add(exec_group)
        
        client.force_login(exec_user)
        res1 = reservation_setup['res1']  # created_by is authorized_user
        
        url = reverse('inventory:reservation-release', kwargs={'pk': res1.pk})
        response = client.post(url)
        assert response.status_code == 302
        assert not StockReservation.objects.filter(pk=res1.pk).exists()

    def test_superuser_can_release_other_user_reservation_success(self, client, db, reservation_setup):
        # Create a superuser
        super_user = User.objects.create_superuser(username='super_user', email='admin@example.com', password='password123')
        
        client.force_login(super_user)
        res1 = reservation_setup['res1']  # created_by is authorized_user
        
        url = reverse('inventory:reservation-release', kwargs={'pk': res1.pk})
        response = client.post(url)
        assert response.status_code == 302
        assert not StockReservation.objects.filter(pk=res1.pk).exists()

