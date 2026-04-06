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
