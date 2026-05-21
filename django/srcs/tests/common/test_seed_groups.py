"""
Tests for seed_groups management command

Tests cover:
- All 4 groups are created
- Correct permission count per group
- Exclusive has full catalog CRUD
- Stock controller / sales rep / warehouse admin are catalog view-only
- Command is idempotent (safe to run twice)
- Admin role uses is_superuser (no group needed)
"""

import pytest
from django.core.management import call_command
from django.contrib.auth.models import Group, Permission, User


@pytest.fixture(autouse=True)
def seed(db):
    """Run seed_groups before every test."""
    call_command('seed_groups')


# ============================================================
# Group Creation
# ============================================================
class TestGroupCreation:

    def test_executive_group_exists(self):
        assert Group.objects.filter(name='executive').exists()

    def test_stock_controller_group_exists(self):
        assert Group.objects.filter(name='stock_controller').exists()

    def test_sales_rep_group_exists(self):
        assert Group.objects.filter(name='sales_rep').exists()

    def test_warehouse_admin_group_exists(self):
        assert Group.objects.filter(name='warehouse_admin').exists()

    def test_exactly_4_groups_created(self):
        group_names = {'executive', 'stock_controller', 'sales_rep', 'warehouse_admin'}
        created = set(Group.objects.filter(name__in=group_names).values_list('name', flat=True))
        assert created == group_names


# ============================================================
# Permission Assignments
# ============================================================
class TestPermissionAssignment:

    def test_executive_has_full_crud(self):
        group = Group.objects.get(name='executive')
        codenames = set(group.permissions.values_list('codename', flat=True))
        
        # Catalog
        for model in ['category', 'item', 'itemimage', 'itempackaging']:
            for action in ['add', 'change', 'delete', 'view']:
                assert f'{action}_{model}' in codenames
        
        # Inventory
        for model in ['warehouse', 'inventorymovement']:
            for action in ['add', 'change', 'delete', 'view']:
                assert f'{action}_{model}' in codenames

    def test_executive_has_24_permissions(self):
        group = Group.objects.get(name='executive')
        assert group.permissions.count() == 24

    def test_stock_controller_permissions(self):
        group = Group.objects.get(name='stock_controller')
        codenames = set(group.permissions.values_list('codename', flat=True))
        assert codenames == {
            # View catalog (read-only)
            'view_category',
            'view_item',
            'view_itemimage',
            'view_itempackaging',
            # View Inventory
            'view_warehouse',
            'view_inventorymovement',
            'view_stock',
            # Full partner permissions
            'add_partner',
            'change_partner',
            'delete_partner',
            'view_partner',
            # Full procurement permissions
            'add_purchaseorder',
            'change_purchaseorder',
            'delete_purchaseorder',
            'view_purchaseorder',
            'add_arrival',
            'change_arrival',
            'delete_arrival',
            'view_arrival',
            'add_shortage',
            'change_shortage',
            'delete_shortage',
            'view_shortage',
        }

    def test_sales_rep_permissions(self):
        group = Group.objects.get(name='sales_rep')
        codenames = set(group.permissions.values_list('codename', flat=True))
        assert codenames == {
            'view_category', 'view_item', 'view_itemimage', 'view_itempackaging',
            'view_warehouse', 'view_inventorymovement'
        }

    def test_warehouse_admin_permissions(self):
        group = Group.objects.get(name='warehouse_admin')
        codenames = set(group.permissions.values_list('codename', flat=True))
        assert codenames == {
            # Full Catalog
            ## Catalog Category permissions
            'add_category',
            'change_category',
            'delete_category',
            'view_category',
            ## Catalog Item permissions
            'add_item',
            'change_item',
            'delete_item',
            'view_item',
            ## Catalog Item Image permissions
            'add_itemimage',
            'change_itemimage',
            'delete_itemimage',
            'view_itemimage',
            ## Catalog Item Packaging permissions
            'add_itempackaging',
            'change_itempackaging',
            'delete_itempackaging',
            'view_itempackaging',
            # Full Warehouse Access (operational)
            ## Inventory Warehouse permissions
            'add_warehouse',
            'change_warehouse',
            'delete_warehouse',
            'view_warehouse',
            ## Inventory Movement Permissions
            'add_inventorymovement',
            'change_inventorymovement',
            'delete_inventorymovement',
            'view_inventorymovement',
            ## Inventory Balances Permissions
            'view_stock',
            ## Inventory Ledger Permissions
            'view_stockcard',
            'add_stockcard',
            'change_stockcard',
            'delete_stockcard',
            # Full partner permissions
            'add_partner',
            'change_partner',
            'delete_partner',
            'view_partner',
            # Procurement Arrivals permissions for receiving
            'view_arrival',
            'change_arrival',
        }


# ============================================================
# Idempotent (safe to run multiple times)
# ============================================================
class TestIdempotent:

    def test_running_twice_does_not_duplicate_groups(self):
        call_command('seed_groups')  # second run (first is autouse fixture)
        assert Group.objects.filter(name='executive').count() == 1

    def test_running_twice_does_not_duplicate_permissions(self):
        call_command('seed_groups')
        group = Group.objects.get(name='executive')
        assert group.permissions.count() == 24


# ============================================================
# Admin Role
# ============================================================
class TestAdminRole:

    def test_superuser_has_all_permissions_without_group(self):
        admin = User.objects.create_superuser(
            username='admin', password='admin123',
        )
        # Superuser bypasses permission checks entirely
        assert admin.has_perm('catalog.add_category') is True
        assert admin.has_perm('catalog.delete_item') is True
        assert admin.groups.count() == 0


# ============================================================
# User Group Assignment
# ============================================================
class TestUserGroupAssignment:

    def test_user_in_executive_group_has_catalog_crud(self):
        user = User.objects.create_user(username='exc_user', password='pass123')
        user.groups.add(Group.objects.get(name='executive'))
        assert user.has_perm('catalog.add_category') is True
        assert user.has_perm('catalog.delete_item') is True

    def test_user_in_sales_rep_can_view_but_not_add(self):
        user = User.objects.create_user(username='sales_user', password='pass123')
        user.groups.add(Group.objects.get(name='sales_rep'))
        assert user.has_perm('catalog.view_item') is True
        assert user.has_perm('catalog.add_item') is False

    def test_user_in_stock_controller_can_view_but_not_delete(self):
        user = User.objects.create_user(username='stock_user', password='pass123')
        user.groups.add(Group.objects.get(name='stock_controller'))
        assert user.has_perm('catalog.view_category') is True
        assert user.has_perm('catalog.delete_category') is False
