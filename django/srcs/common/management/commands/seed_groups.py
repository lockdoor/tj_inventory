"""
Management command: seed_groups

Creates Django Groups with assigned Permissions based on the role
definitions in docs/role.md.

Usage:
    python manage.py seed_groups

This command is idempotent — safe to run multiple times.
Groups that already exist will be updated with the correct permissions.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission


# ---------------------------------------------------------------------------
# Role → Permission mapping
#
# Format:  'group_name': ['app_label.codename', ...]
#
# Django auto-creates these codenames for every model:
#   add_<model>  |  change_<model>  |  delete_<model>  |  view_<model>
#
# As new apps are added (inventory, orders, etc.), add their permissions here.
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS = {
    'executive': [
        # Full access to catalog
        'catalog.add_category',
        'catalog.change_category',
        'catalog.delete_category',
        'catalog.view_category',
        'catalog.add_item',
        'catalog.change_item',
        'catalog.delete_item',
        'catalog.view_item',
        'catalog.add_itemimage',
        'catalog.change_itemimage',
        'catalog.delete_itemimage',
        'catalog.view_itemimage',
        # Inventory Permissions
        'inventory.add_warehouse',
        'inventory.change_warehouse',
        'inventory.delete_warehouse',
        'inventory.view_warehouse',
        # Inventory Movement Permissions
        'inventory.add_inventorymovement',
        'inventory.change_inventorymovement',
        'inventory.delete_inventorymovement',
        'inventory.view_inventorymovement',
    ],

    'stock_controller': [
        # View catalog (read-only)
        'catalog.view_category',
        'catalog.view_item',
        'catalog.view_itemimage',
        # View Inventory
        'inventory.view_warehouse',
        'inventory.view_inventorymovement',
        'inventory.view_stock',
        
        # Full partner permissions
        'partners.add_partner',
        'partners.change_partner',
        'partners.delete_partner',
        'partners.view_partner',
        # Full procurement permissions
        'procurement.add_purchaseorder',
        'procurement.change_purchaseorder',
        'procurement.delete_purchaseorder',
        'procurement.view_purchaseorder',
        'procurement.add_arrival',
        'procurement.change_arrival',
        'procurement.delete_arrival',
        'procurement.view_arrival',
        'procurement.add_shortage',
        'procurement.change_shortage',
        'procurement.delete_shortage',
        'procurement.view_shortage',
    ],

    'sales_rep': [
        # View catalog (read-only)
        'catalog.view_category',
        'catalog.view_item',
        'catalog.view_itemimage',
        # View Inventory
        'inventory.view_warehouse',
        'inventory.view_inventorymovement',
    ],

    'warehouse_admin': [
        # Full Catalog
        ## Catalog Category permissions
        'catalog.add_category',
        'catalog.change_category',
        'catalog.delete_category',
        'catalog.view_category',
        ## Catalog Item permissions
        'catalog.add_item',
        'catalog.change_item',
        'catalog.delete_item',
        'catalog.view_item',
        ## Catalog Item Image permissions
        'catalog.add_itemimage',
        'catalog.change_itemimage',
        'catalog.delete_itemimage',
        'catalog.view_itemimage',
        # Full Warehouse Access (operational)
        ## Inventory Warehouse permissions
        'inventory.add_warehouse',
        'inventory.change_warehouse',
        'inventory.delete_warehouse',
        'inventory.view_warehouse',
        ## Inventory Movement Permissions
        'inventory.add_inventorymovement',
        'inventory.change_inventorymovement',
        'inventory.delete_inventorymovement',
        'inventory.view_inventorymovement',
        ## Inventory Balances Permissions
        'inventory.view_stock',
        ## Inventory Ledger Permissions
        'inventory.view_stockcard',
        'inventory.add_stockcard',
        'inventory.change_stockcard',
        'inventory.delete_stockcard',
        # Full partner permissions
        'partners.add_partner',
        'partners.change_partner',
        'partners.delete_partner',
        'partners.view_partner',
    ],
}


class Command(BaseCommand):
    help = 'Create or update groups and assign permissions based on role definitions.'

    def handle(self, *args, **options):
        for group_name, perm_codes in ROLE_PERMISSIONS.items():
            group, created = Group.objects.get_or_create(name=group_name)
            action = 'Created' if created else 'Updated'

            # Resolve permission objects
            permissions = []
            for code in perm_codes:
                app_label, codename = code.split('.')
                try:
                    perm = Permission.objects.get(
                        content_type__app_label=app_label,
                        codename=codename,
                    )
                    permissions.append(perm)
                except Permission.DoesNotExist:
                    self.stderr.write(
                        self.style.WARNING(f"  ⚠ Permission not found: {code}")
                    )

            # Replace all permissions (idempotent)
            group.permissions.set(permissions)

            self.stdout.write(
                self.style.SUCCESS(
                    f"  ✓ {action} group '{group_name}' "
                    f"with {len(permissions)} permissions"
                )
            )

        self.stdout.write(self.style.SUCCESS('\nDone. All groups are up to date.'))
        self.stdout.write(
            self.style.NOTICE(
                '\nNote: Admin users use is_superuser=True '
                '(no group needed).'
            )
        )
