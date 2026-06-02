from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin

class InventoryOverviewView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Main overview for the Inventory module.
    Displays cards for Warehouse, Movement, Stock, and StockCard management.
    """
    template_name = 'inventory/overview.html'
    permission_required = 'inventory.view_warehouse'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Inventory Overview"
        context['modules'] = [
            {
                'title': 'Warehouses',
                'description': 'Manage physical storage locations, capacity, and active status.',
                'url': 'inventory:warehouse-list',
                'icon_name': 'warehouse',
                'icon_class': 'warehouse-icon',
                'badge': 'Structure'
            },
            {
                'title': 'Movements',
                'description': 'Create or update Inbound and Outbound documents (Stock Entries).',
                'url': 'inventory:movement-list',
                'icon_name': 'arrow-left-right',
                'icon_class': 'movement-icon',
                'badge': 'Operations'
            },
            {
                'title': 'Stock Balances',
                'description': 'Real-time visibility of available quantity per LOT and Location.',
                'url': 'inventory:stock-balance-list',
                'icon_name': 'package',
                'icon_class': 'stock-icon',
                'badge': 'Inventory'
            },
            {
                'title': 'Stock Cards',
                'description': 'Immutable audit ledger for every transaction history.',
                'url': 'inventory:stockcard-list',
                'icon_name': 'scroll',
                'icon_class': 'ledger-icon',
                'badge': 'Audit Ledger'
            },
            {
                'title': 'Stock Reservations',
                'description': 'Monitor physical stock locks and active allocation holds.',
                'url': 'inventory:reservation-list',
                'icon_name': 'lock',
                'icon_class': 'reservation-icon',
                'badge': 'Holds'
            }
        ]
        return context
