import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from django.core.management import call_command
from inventory.models import InventoryMovement, Warehouse

@pytest.fixture(autouse=True)
def seed_groups(db):
    """Seed groups and permissions before each test."""
    call_command('seed_groups')

@pytest.fixture
def user_no_perms(db):
    """User with zero inventory permissions."""
    return User.objects.create_user(username='guest', password='password123')

@pytest.fixture
def user_view_only(db):
    """User with only view_inventorymovement permission."""
    user = User.objects.create_user(username='viewer', password='password123')
    perm = Permission.objects.get(codename='view_inventorymovement')
    user.user_permissions.add(perm)
    return user

@pytest.fixture
def warehouse(db, user_no_perms):
    """A sample warehouse for movements."""
    return Warehouse.objects.create(
        name="Main Hub",
        code="WH001",
        created_by=user_no_perms
    )

@pytest.mark.django_db
class TestMovementListView:
    """
    Tests for the Movement List view:
    - Logic: Pagination (10 per page)
    - Security: Permission gating (view_inventorymovement)
    """

    def test_movement_list_permission_denied(self, client, user_no_perms):
        """Verify that users without permission get 403."""
        url = reverse('inventory:movement-list')
        client.login(username='guest', password='password123')
        response = client.get(url)
        assert response.status_code == 403

    def test_movement_list_permission_granted(self, client, user_view_only):
        """Verify that users with permission get 200."""
        url = reverse('inventory:movement-list')
        client.login(username='viewer', password='password123')
        response = client.get(url)
        assert response.status_code == 200

    def test_movement_list_pagination(self, client, user_view_only, warehouse):
        """Verify that the list paginates at 10 items."""
        # Create 15 movements
        from django.utils import timezone
        for i in range(15):
            InventoryMovement.objects.create(
                document_no=f"MOV-{i:03d}",
                type=InventoryMovement.MovementType.INBOUND,
                date=timezone.now().date(),
                warehouse=warehouse,
                created_by=user_view_only
            )
        
        url = reverse('inventory:movement-list')
        client.login(username='viewer', password='password123')
        
        # Check first page (should have 10)
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context['movements']) == 10
        assert response.context['is_paginated'] is True
        
        # Check second page (should have 5)
        response = client.get(url + '?page=2')
        assert response.status_code == 200
        assert len(response.context['movements']) == 5

from django.utils import timezone

@pytest.mark.django_db
class TestMovementDetailView:
    """
    Tests for the Movement Detail view:
    - Security: Permission gating
    - Logic: Correct object retrieval via document_no
    """

    def test_movement_detail_permission_denied(self, client, user_no_perms, warehouse):
        """Verify that users without permission get 403."""
        movement = InventoryMovement.objects.create(
            document_no="MOV-DET-001",
            type=InventoryMovement.MovementType.INBOUND,
            date=timezone.now().date(),
            warehouse=warehouse,
            created_by=user_no_perms
        )
        url = reverse('inventory:movement-detail', kwargs={'document_no': movement.document_no})
        client.login(username='guest', password='password123')
        response = client.get(url)
        assert response.status_code == 403

    def test_movement_detail_permission_granted(self, client, user_view_only, warehouse):
        """Verify that users with permission get 200."""
        movement = InventoryMovement.objects.create(
            document_no="MOV-DET-002",
            type=InventoryMovement.MovementType.INBOUND,
            date=timezone.now().date(),
            warehouse=warehouse,
            created_by=user_view_only
        )
        url = reverse('inventory:movement-detail', kwargs={'document_no': movement.document_no})
        client.login(username='viewer', password='password123')
        response = client.get(url)
        assert response.status_code == 200
        assert response.context['movement'].document_no == "MOV-DET-002"

    def test_movement_detail_404(self, client, user_view_only):
        """Verify that missing documents return 404."""
        url = reverse('inventory:movement-detail', kwargs={'document_no': 'NON-EXISTENT'})
        client.login(username='viewer', password='password123')
        response = client.get(url)
        assert response.status_code == 404

    def test_movement_detail_completed_with_audit(self, client, user_view_only, warehouse):
        """Verify that completed movements show their audit trail."""
        from catalog.models import Item
        from inventory.models import InventoryMovementItem, Stock, StockCard
        
        # 1. Setup Data
        item = Item.objects.create(sku="SKU-AUDIT", name="Audit Item", created_by=user_view_only)
        movement = InventoryMovement.objects.create(
            document_no="MOV-COMPLETED",
            type=InventoryMovement.MovementType.INBOUND,
            status=InventoryMovement.Status.COMPLETED,
            date=timezone.now().date(),
            warehouse=warehouse,
            created_by=user_view_only
        )
        mov_item = InventoryMovementItem.objects.create(
            movement=movement,
            item=item,
            lot_number="LOT-001",
            quantity=10
        )
        stock = Stock.objects.create(warehouse=warehouse, item=item, lot_number="LOT-001", balance=10, created_by=user_view_only)
        StockCard.objects.create(
            stock=stock,
            warehouse=warehouse,
            item=item,
            lot_number="LOT-001",
            movement_item=mov_item,
            quantity=10,
            type=StockCard.StockCardType.IN,
            created_by=user_view_only
        )

        # 2. Verify View
        url = reverse('inventory:movement-detail', kwargs={'document_no': movement.document_no})
        client.login(username='viewer', password='password123')
        response = client.get(url)
        
        assert response.status_code == 200
        assert 'audit_trail' in response.context
        assert len(response.context['audit_trail']) == 1
        assert len(response.context['audit_trail']) == 1
        assert response.context['audit_trail'][0].movement_item.movement == movement

@pytest.fixture
def user_add_perm(db):
    """User with add_inventorymovement permission."""
    user = User.objects.create_user(username='creator', password='password123')
    perm = Permission.objects.get(codename='add_inventorymovement')
    user.user_permissions.add(perm)
    return user

@pytest.mark.django_db
class TestMovementCreateView:
    """
    Tests for the Movement Create view:
    - Security: Permission gating (add_inventorymovement)
    - Logic: Atomic creation of Header + Items
    - Validation: Mandatory items rule
    """

    def test_movement_create_permission_denied(self, client, user_view_only):
        """Verify that users without 'add' permission get 403."""
        url = reverse('inventory:movement-create')
        client.login(username='viewer', password='password123')
        response = client.get(url)
        assert response.status_code == 403

    def test_movement_create_permission_granted(self, client, user_add_perm):
        """Verify that users with 'add' permission get 200."""
        url = reverse('inventory:movement-create')
        client.login(username='creator', password='password123')
        response = client.get(url)
        assert response.status_code == 200

    def test_movement_create_success(self, client, user_add_perm, warehouse):
        """Verify successful creation of movement with items."""
        from catalog.models import Item
        item = Item.objects.create(sku="SKU-CREATE-1", name="Create Item", created_by=user_add_perm)
        
        url = reverse('inventory:movement-create')
        client.login(username='creator', password='password123')
        
        post_data = {
            'document_no': 'MOV-SUCCESS-001',
            'type': 'inbound',
            'date': timezone.now().date(),
            'warehouse': warehouse.id,
            'note': 'Test success',
            # FormSet Management Form
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
            # FormSet Data
            'items-0-item': item.id,
            'items-0-lot_number': 'LOT-X',
            'items-0-quantity': '50',
        }
        
        response = client.post(url, post_data)
        
        # Verify redirect to detail view
        assert response.status_code == 302
        assert response.url == reverse('inventory:movement-detail', kwargs={'document_no': 'MOV-SUCCESS-001'})
        
        # Verify database records
        movement = InventoryMovement.objects.get(document_no='MOV-SUCCESS-001')
        assert movement.items.count() == 1
        assert movement.items.first().quantity == 50
        assert movement.status == 'draft'

    def test_movement_create_no_items_fail(self, client, user_add_perm, warehouse):
        """Verify that creating a movement without items fails validation."""
        url = reverse('inventory:movement-create')
        client.login(username='creator', password='password123')
        
        post_data = {
            'document_no': 'MOV-FAIL-001',
            'type': 'inbound',
            'date': timezone.now().date(),
            'warehouse': warehouse.id,
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            # We provide the form but leave item empty
            'items-0-item': '',
            'items-0-quantity': '',
        }
        
        response = client.post(url, post_data)
        
        # Should stay on page and show error
        assert response.status_code == 200
        assert not InventoryMovement.objects.filter(document_no='MOV-FAIL-001').exists()
        # Formset error should be in context
        assert response.context['items'].errors
        