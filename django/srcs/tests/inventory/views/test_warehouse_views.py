import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Group, Permission
from django.core.management import call_command
from inventory.models import Warehouse

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
    """User with only view_warehouse permission."""
    user = User.objects.create_user(username='viewer', password='password123')
    perm = Permission.objects.get(codename='view_warehouse')
    user.user_permissions.add(perm)
    return user

@pytest.fixture
def user_full_perms(db):
    """User with all warehouse CRUD permissions."""
    user = User.objects.create_user(username='admin_staff', password='password123')
    # Use the executive group which should have all perms from seed_groups
    exec_group = Group.objects.get(name='executive')
    user.groups.add(exec_group)
    return user

@pytest.fixture
def warehouse(db, user_full_perms):
    """A standard active warehouse."""
    return Warehouse.objects.create(
        name="Test Warehouse",
        code="WH-TEST",
        status="active",
        created_by=user_full_perms
    )

@pytest.fixture
def trashed_warehouse(db, user_full_perms):
    """A soft-deleted warehouse."""
    return Warehouse.objects.create(
        name="Deleted Warehouse",
        code="WH-DEL",
        status="active",
        is_deleted=True,
        created_by=user_full_perms,
        deleted_by=user_full_perms
    )

@pytest.mark.django_db
class TestWarehouseViewPermissions:
    """
    Tests for view-level permission gating (RBAC).
    Verifies that raise_exception=True correctly returns 403 Forbidden.
    """

    def test_warehouse_list_permissions(self, client, user_no_perms, user_view_only):
        url = reverse('inventory:warehouse-list')
        
        # 1. Unauthenticated -> 403 (due to raise_exception=True)
        assert client.get(url).status_code == 403
        
        # 2. No Perms -> 403
        client.login(username='guest', password='password123')
        assert client.get(url).status_code == 403
        client.logout()
        
        # 3. View Only -> 200
        client.login(username='viewer', password='password123')
        assert client.get(url).status_code == 200

    def test_warehouse_detail_permissions(self, client, warehouse, user_no_perms, user_view_only):
        url = reverse('inventory:warehouse-detail', kwargs={'code': warehouse.code})
        
        # 1. No Perms -> 403
        client.login(username='guest', password='password123')
        assert client.get(url).status_code == 403
        client.logout()
        
        # 2. View Only -> 200
        client.login(username='viewer', password='password123')
        assert client.get(url).status_code == 200

    def test_warehouse_trash_permissions(self, client, user_view_only, user_full_perms):
        url = reverse('inventory:warehouse-trash')
        
        # 1. View Only (No Delete Perm) -> 403
        client.login(username='viewer', password='password123')
        assert client.get(url).status_code == 403
        client.logout()
        
        # 2. Full Perms (Includes Delete) -> 200
        client.login(username='admin_staff', password='password123')
        assert client.get(url).status_code == 200

    def test_warehouse_create_permissions(self, client, user_view_only, user_full_perms):
        url = reverse('inventory:warehouse-create')
        
        # 1. View Only -> 403
        client.login(username='viewer', password='password123')
        assert client.get(url).status_code == 403
        client.logout()
        
        # 2. Full Perms -> 200
        client.login(username='admin_staff', password='password123')
        assert client.get(url).status_code == 200

    def test_warehouse_update_permissions(self, client, warehouse, user_view_only, user_full_perms):
        url = reverse('inventory:warehouse-update', kwargs={'code': warehouse.code})
        
        # 1. View Only -> 403
        client.login(username='viewer', password='password123')
        assert client.get(url).status_code == 403
        client.logout()
        
        # 2. Full Perms -> 200
        client.login(username='admin_staff', password='password123')
        assert client.get(url).status_code == 200

    def test_warehouse_delete_permissions(self, client, warehouse, user_view_only, user_full_perms):
        url = reverse('inventory:warehouse-delete', kwargs={'code': warehouse.code})
        
        # 1. View Only -> 403
        client.login(username='viewer', password='password123')
        assert client.get(url).status_code == 403
        client.logout()
        
        # 2. Full Perms -> 200
        client.login(username='admin_staff', password='password123')
        assert client.get(url).status_code == 200

    def test_warehouse_restore_permissions(self, client, trashed_warehouse, user_view_only, user_full_perms):
        url = reverse('inventory:warehouse-restore', kwargs={'code': trashed_warehouse.code})
        
        # 1. View Only -> 403
        client.login(username='viewer', password='password123')
        # Restore is POST only
        assert client.post(url).status_code == 403
        client.logout()
        
        # 2. Full Perms -> 302 (Redirect after restore)
        client.login(username='admin_staff', password='password123')
        assert client.post(url).status_code == 302
