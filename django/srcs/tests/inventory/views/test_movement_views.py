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

@pytest.fixture
def user_delete_perm(db):
    """User with delete_inventorymovement permission."""
    user = User.objects.create_user(username='creator', password='password123')
    perm = Permission.objects.get(codename='delete_inventorymovement')
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
            'reference_type': 'none',
            'reference_no': '',
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

    def test_movement_create_with_reference(self, client, user_add_perm, warehouse):
        """Verify successful creation of movement with external reference."""
        from catalog.models import Item
        item = Item.objects.create(sku="SKU-REF-1", name="Ref Item", created_by=user_add_perm)
        
        url = reverse('inventory:movement-create')
        client.login(username='creator', password='password123')
        
        post_data = {
            'document_no': 'MOV-REF-001',
            'type': 'inbound',
            'date': timezone.now().date(),
            'warehouse': warehouse.id,
            'note': 'Test with reference',
            'reference_type': 'production',
            'reference_no': 'PROD-SCHED-2026',
            # FormSet Management Form
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '1',
            'items-MAX_NUM_FORMS': '1000',
            # FormSet Data
            'items-0-item': item.id,
            'items-0-lot_number': 'LOT-REF',
            'items-0-quantity': '100',
        }
        
        response = client.post(url, post_data)
        
        assert response.status_code == 302
        movement = InventoryMovement.objects.get(document_no='MOV-REF-001')
        assert movement.reference_type == 'production'
        assert movement.reference_no == 'PROD-SCHED-2026'

    def test_movement_create_show_error_if_something_wrong(self, client, user_add_perm, warehouse):
        """Verify that creating a movement with an error fails gracefully."""
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

    def test_movement_create_outbound_invalid_lot_fails(self, client, user_add_perm, warehouse):
        """Verify that outbound movements fail if the lot does not exist in stock."""
        from catalog.models import Item
        item = Item.objects.create(sku="SKU-OUT-1", name="Out Item", created_by=user_add_perm)
        
        url = reverse('inventory:movement-create')
        client.login(username='creator', password='password123')
        
        post_data = {
            'document_no': 'MOV-OUT-FAIL',
            'type': 'outbound',
            'date': timezone.now().date(),
            'warehouse': warehouse.id,
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-0-item': item.id,
            'items-0-lot_number': 'NON-EXISTENT-LOT',
            'items-0-quantity': '10',
        }
        
        response = client.post(url, post_data)
        
        assert response.status_code == 200
        # Check for the specific error message added in form clean
        assert f"Lot 'NON-EXISTENT-LOT' not found in {warehouse.name}." in str(response.context['items'].errors)

@pytest.mark.django_db
class TestMovementLifecycleActions:
    """Tests for Complete, Revert, and Delete actions."""
    
    def test_movement_complete_success(self, client, user_add_perm, warehouse):
        from catalog.models import Item
        from inventory.models import Stock, StockCard
        item = Item.objects.create(sku="SKU-COMP", name="Comp Item", created_by=user_add_perm)
        movement = InventoryMovement.objects.create(
            document_no="MOV-DRAFT-1", type='inbound', date=timezone.now().date(),
            warehouse=warehouse, created_by=user_add_perm, status='draft'
        )
        from inventory.models import InventoryMovementItem
        InventoryMovementItem.objects.create(movement=movement, item=item, lot_number="LOT-001", quantity=50)
        
        client.login(username='creator', password='password123')
        url = reverse('inventory:movement-complete', kwargs={'document_no': movement.document_no})
        
        response = client.post(url)
        assert response.status_code == 302
        
        movement.refresh_from_db()
        assert movement.status == 'completed'
        assert Stock.objects.get(lot_number="LOT-001").balance == 50
        assert StockCard.objects.filter(movement_item__movement=movement).count() == 1

    def test_movement_revert_success(self, client, user_add_perm, warehouse):
        from catalog.models import Item
        from inventory.models import Stock, StockCard
        item = Item.objects.create(sku="SKU-REV", name="Rev Item", created_by=user_add_perm)
        movement = InventoryMovement.objects.create(
            document_no="MOV-FOR-REV", type='inbound', status='completed',
            date=timezone.now().date(), warehouse=warehouse, created_by=user_add_perm
        )
        # Manually create fulfillment side effects
        from inventory.models import InventoryMovementItem
        mov_item = InventoryMovementItem.objects.create(movement=movement, item=item, lot_number="LOT-002", quantity=20)
        Stock.objects.create(warehouse=warehouse, item=item, lot_number="LOT-002", balance=20, created_by=user_add_perm)
        
        client.login(username='creator', password='password123')
        url = reverse('inventory:movement-revert', kwargs={'document_no': movement.document_no})
        
        response = client.post(url)
        assert response.status_code == 302
        
        movement.refresh_from_db()
        assert movement.status == 'draft'
        assert Stock.objects.get(lot_number="LOT-002").balance == 0
        # Should have 1 reversal card (fulfillment not tracked here since we manually bypassed it)
        # Actually in revert_to_draft it creates a StockCard
        assert StockCard.objects.filter(note__contains="REVERSION").count() == 1

    def test_movement_delete_draft_success(self, client, user_delete_perm, warehouse):
        movement = InventoryMovement.objects.create(
            document_no="MOV-DELETE-ME", type='inbound', date=timezone.now().date(),
            warehouse=warehouse, created_by=user_delete_perm, status='draft'
        )
        client.login(username='creator', password='password123')
        url = reverse('inventory:movement-delete', kwargs={'document_no': movement.document_no})
        
        response = client.post(url)
        assert response.status_code == 302
        
        movement.refresh_from_db()
        assert movement.is_deleted is True