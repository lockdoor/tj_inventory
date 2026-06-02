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
        'catalog.add_itempackaging',
        'catalog.change_itempackaging',
        'catalog.delete_itempackaging',
        'catalog.view_itempackaging',

        # Full access to inventory
        'inventory.add_warehouse',
        'inventory.change_warehouse',
        'inventory.delete_warehouse',
        'inventory.view_warehouse',
        'inventory.add_inventorymovement',
        'inventory.change_inventorymovement',
        'inventory.delete_inventorymovement',
        'inventory.view_inventorymovement',
        'inventory.add_inventorymovementitem',
        'inventory.change_inventorymovementitem',
        'inventory.delete_inventorymovementitem',
        'inventory.view_inventorymovementitem',
        'inventory.add_stock',
        'inventory.change_stock',
        'inventory.delete_stock',
        'inventory.view_stock',
        'inventory.add_stockcard',
        'inventory.change_stockcard',
        'inventory.delete_stockcard',
        'inventory.view_stockcard',
        'inventory.add_stockreservation',
        'inventory.change_stockreservation',
        'inventory.delete_stockreservation',
        'inventory.view_stockreservation',
        'inventory.add_inventorymovementattachment',
        'inventory.change_inventorymovementattachment',
        'inventory.delete_inventorymovementattachment',
        'inventory.view_inventorymovementattachment',

        # Full access to partners
        'partners.add_partner',
        'partners.change_partner',
        'partners.delete_partner',
        'partners.view_partner',

        # Full access to procurement
        'procurement.add_purchaseorder',
        'procurement.change_purchaseorder',
        'procurement.delete_purchaseorder',
        'procurement.view_purchaseorder',
        'procurement.add_purchaseorderitem',
        'procurement.change_purchaseorderitem',
        'procurement.delete_purchaseorderitem',
        'procurement.view_purchaseorderitem',
        'procurement.add_arrival',
        'procurement.change_arrival',
        'procurement.delete_arrival',
        'procurement.view_arrival',
        'procurement.add_arrivalitem',
        'procurement.change_arrivalitem',
        'procurement.delete_arrivalitem',
        'procurement.view_arrivalitem',
        'procurement.add_shortage',
        'procurement.change_shortage',
        'procurement.delete_shortage',
        'procurement.view_shortage',
        'procurement.add_arrivalreservation',
        'procurement.change_arrivalreservation',
        'procurement.delete_arrivalreservation',
        'procurement.view_arrivalreservation',
        'procurement.add_purchaseorderattachment',
        'procurement.change_purchaseorderattachment',
        'procurement.delete_purchaseorderattachment',
        'procurement.view_purchaseorderattachment',
        'procurement.add_arrivalattachment',
        'procurement.change_arrivalattachment',
        'procurement.delete_arrivalattachment',
        'procurement.view_arrivalattachment',

        # Full access to sales
        'sales.add_salesorder',
        'sales.change_salesorder',
        'sales.delete_salesorder',
        'sales.view_salesorder',
        'sales.add_salesorderitem',
        'sales.change_salesorderitem',
        'sales.delete_salesorderitem',
        'sales.view_salesorderitem',
        'sales.add_salesallocation',
        'sales.change_salesallocation',
        'sales.delete_salesallocation',
        'sales.view_salesallocation',
    ],

    'stock_controller': [
        # View catalog (read-only)
        'catalog.view_category',
        'catalog.view_item',
        'catalog.view_itemimage',
        'catalog.view_itempackaging',
        # View Inventory
        'inventory.view_warehouse',
        'inventory.view_inventorymovement',
        'inventory.view_inventorymovementitem',
        'inventory.view_stock',
        'inventory.view_stockcard',
        'inventory.view_stockreservation',
        
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
        'procurement.add_purchaseorderitem',
        'procurement.change_purchaseorderitem',
        'procurement.delete_purchaseorderitem',
        'procurement.view_purchaseorderitem',
        'procurement.add_arrival',
        'procurement.change_arrival',
        'procurement.delete_arrival',
        'procurement.view_arrival',
        'procurement.add_arrivalitem',
        'procurement.change_arrivalitem',
        'procurement.delete_arrivalitem',
        'procurement.view_arrivalitem',
        'procurement.add_shortage',
        'procurement.change_shortage',
        'procurement.delete_shortage',
        'procurement.view_shortage',
        'procurement.add_arrivalreservation',
        'procurement.change_arrivalreservation',
        'procurement.delete_arrivalreservation',
        'procurement.view_arrivalreservation',
        'procurement.add_purchaseorderattachment',
        'procurement.change_purchaseorderattachment',
        'procurement.delete_purchaseorderattachment',
        'procurement.view_purchaseorderattachment',
        'procurement.add_arrivalattachment',
        'procurement.change_arrivalattachment',
        'procurement.delete_arrivalattachment',
        'procurement.view_arrivalattachment',
    ],

    'sales_rep': [
        # View catalog (read-only)
        'catalog.view_category',
        'catalog.view_item',
        'catalog.view_itemimage',
        'catalog.view_itempackaging',
        # View Inventory
        'inventory.view_warehouse',
        'inventory.view_inventorymovement',
        'inventory.view_inventorymovementitem',
        'inventory.view_stock',
        'inventory.view_stockcard',
        # Full Partner/Customer permissions
        'partners.add_partner',
        'partners.change_partner',
        'partners.delete_partner',
        'partners.view_partner',
        # Full Permission sales_order
        'sales.add_salesorder',
        'sales.change_salesorder',
        'sales.delete_salesorder',
        'sales.view_salesorder',
        'sales.add_salesorderitem',
        'sales.change_salesorderitem',
        'sales.delete_salesorderitem',
        'sales.view_salesorderitem',
        # Full Permission allocation
        'sales.add_salesallocation',
        'sales.change_salesallocation',
        'sales.delete_salesallocation',
        'sales.view_salesallocation',
        # Full Reservation permissions
        'inventory.add_stockreservation',
        'inventory.change_stockreservation',
        'inventory.delete_stockreservation',
        'inventory.view_stockreservation',
        'procurement.add_arrivalreservation',
        'procurement.change_arrivalreservation',
        'procurement.delete_arrivalreservation',
        'procurement.view_arrivalreservation',
    ],

    'warehouse_admin': [
        # Full Catalog
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
        'catalog.add_itempackaging',
        'catalog.change_itempackaging',
        'catalog.delete_itempackaging',
        'catalog.view_itempackaging',
        # Full Warehouse Access (operational)
        'inventory.add_warehouse',
        'inventory.change_warehouse',
        'inventory.delete_warehouse',
        'inventory.view_warehouse',
        'inventory.add_inventorymovement',
        'inventory.change_inventorymovement',
        'inventory.delete_inventorymovement',
        'inventory.view_inventorymovement',
        'inventory.add_inventorymovementitem',
        'inventory.change_inventorymovementitem',
        'inventory.delete_inventorymovementitem',
        'inventory.view_inventorymovementitem',
        'inventory.view_stock',
        'inventory.add_stockcard',
        'inventory.change_stockcard',
        'inventory.delete_stockcard',
        'inventory.view_stockcard',
        # Full Partner/Customer permissions
        'partners.add_partner',
        'partners.change_partner',
        'partners.delete_partner',
        'partners.view_partner',
        # Procurement Arrivals permissions for receiving
        'procurement.view_arrival',
        'procurement.change_arrival',
        'procurement.view_arrivalitem',
        'procurement.change_arrivalitem',
        'procurement.add_arrivalattachment',
        'procurement.change_arrivalattachment',
        'procurement.delete_arrivalattachment',
        'procurement.view_arrivalattachment',
        # Update Reservation permissions
        'inventory.add_stockreservation',
        'inventory.change_stockreservation',
        'inventory.delete_stockreservation',
        'inventory.view_stockreservation',
        'procurement.add_arrivalreservation',
        'procurement.change_arrivalreservation',
        'procurement.delete_arrivalreservation',
        'procurement.view_arrivalreservation',
        # Shortages / discrepancies
        'procurement.add_shortage',
        'procurement.change_shortage',
        'procurement.delete_shortage',
        'procurement.view_shortage',
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

        self.seed_default_user()

    def seed_default_user(self):
        '''use in development only'''
        from django.contrib.auth.models import User
        
        admin = User.objects.filter(username='admin').first()
        if not admin:
            admin = User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('✓ Created superuser "admin"'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Superuser "admin" already exists.'))

        whadmin = User.objects.filter(username='whadmin').first()
        if not whadmin:
            whadmin = User.objects.create_user('whadmin', 'whadmin@example.com', 'tj123456')
            self.stdout.write(self.style.SUCCESS('✓ Created user "whadmin"'))
            whadmin.groups.add(Group.objects.get(name='warehouse_admin'))
            self.stdout.write(self.style.SUCCESS('✓ Added user "whadmin" to group "warehouse_admin"'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ User "whadmin" already exists.'))

        stctrl = User.objects.filter(username='stctrl').first()
        if not stctrl:
            stctrl = User.objects.create_user('stctrl', 'stctrl@example.com', 'tj123456')
            self.stdout.write(self.style.SUCCESS('✓ Created user "stctrl"'))
            stctrl.groups.add(Group.objects.get(name='stock_controller'))
            self.stdout.write(self.style.SUCCESS('✓ Added user "stctrl" to group "stock_control"'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ User "stctrl" already exists.'))

        sale= User.objects.filter(username='sale').first()
        if not sale:
            sale = User.objects.create_user('sale', 'sale@example.com', 'tj123456')
            self.stdout.write(self.style.SUCCESS('✓ Created user "sale"'))
            sale.groups.add(Group.objects.get(name='sales_rep'))
            self.stdout.write(self.style.SUCCESS('✓ Added user "sale" to group "sales_rep"'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ User "sale" already exists.'))
        