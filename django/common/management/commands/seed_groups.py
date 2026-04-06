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
    ],

    'stock_controller': [
        # View catalog (read-only)
        'catalog.view_category',
        'catalog.view_item',
        'catalog.view_itemimage',
        # View Inventory
        'inventory.view_warehouse',
    ],

    'sales_rep': [
        # View catalog (read-only)
        'catalog.view_category',
        'catalog.view_item',
        'catalog.view_itemimage',
        # View Inventory
        'inventory.view_warehouse',
    ],

    'warehouse_admin': [
        # View catalog (read-only)
        'catalog.view_category',
        'catalog.view_item',
        'catalog.view_itemimage',
        # Full Warehouse Access (operational)
        'inventory.add_warehouse',
        'inventory.change_warehouse',
        'inventory.delete_warehouse',
        'inventory.view_warehouse',
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
