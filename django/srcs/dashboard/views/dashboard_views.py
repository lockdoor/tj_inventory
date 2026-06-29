from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    The main landing page of the application after logging in.
    Automatically serves a specialized dashboard based on the user's group.
    """

    def get_role(self):
        """
        Determines the effective role of the user based on group membership.
        Priority: Executive > Stock Controller > Warehouse Admin > Sales Rep > Default (Executive)
        """
        groups = self.request.user.groups.values_list('name', flat=True)
        if 'executive' in groups or self.request.user.is_superuser:
            return 'executive'
        if 'stock_controller' in groups:
            return 'stock_controller'
        if 'warehouse_admin' in groups:
            return 'warehouse_admin'
        if 'sales_rep' in groups:
            return 'sales_rep'
        return 'executive' # Fallback

    def get_template_names(self):
        role = self.get_role()
        if role == 'warehouse_admin':
            return ['dashboard/warehouse_dashboard.html']
        if role == 'stock_controller':
            return ['dashboard/stock_controller_dashboard.html']
        if role == 'sales_rep':
            return ['dashboard/sales_dashboard.html']
        return ['dashboard/executive_dashboard.html']

    def get_context_data(self, **kwargs):
        role = self.get_role()
        if role == 'warehouse_admin':
            return self.get_warehouse_context(**kwargs)
        if role == 'stock_controller':
            return self.get_stock_controller_context(**kwargs)
        if role == 'sales_rep':
            return self.get_sales_context(**kwargs)
        return self.get_executive_context(**kwargs)

    def get_executive_context(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Executive Dashboard"
        context['modules'] = [
            {
                'title': 'Catalog Management',
                'description': 'Manage product categories, items, and audit history.',
                'url': 'catalog:catalog-overview',
                'icon_name': 'box',
                'badge': 'Product Master'
            },
            {
                'title': 'Partner Database',
                'description': 'Track your global suppliers and customer network.',
                'url': 'partners:partner-list',
                'icon_name': 'users',
                'badge': 'External Entities'
            },
            {
                'title': 'Inventory Engine',
                'description': 'Monitor warehouses, stock balances, movements, and physical stock allocations.',
                'url': 'inventory:overview',
                'icon_name': 'database',
                'badge': 'Core Engine'
            },
            {
                'title': 'Procurement Operations',
                'description': 'Manage purchase orders, incoming arrivals, shortages, and arrival pre-allocations.',
                'url': 'procurement:overview',
                'icon_name': 'shopping-cart',
                'badge': 'Procurement'
            },
            {
                'title': 'Sales & Demand',
                'description': 'Track sales orders, customer demands, and stock reservation allocations.',
                'url': 'sales:overview',
                'icon_name': 'shopping-bag',
                'badge': 'Sells'
            },
        ]
        return context

    def get_warehouse_context(self, **kwargs):
        from inventory.services.stock_service import StockService
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Warehouse Control Center"
        
        # Specific metrics for warehouse role
        context['stats'] = StockService.get_dashboard_metrics()
        
        # Limited modules for warehouse role
        context['modules'] = [
            {
                'title': 'Inventory Operations',
                'description': 'Manage stock balances, lots, and warehouse structure.',
                'url': 'inventory:overview',
                'icon_name': 'package',
                'badge': 'Operations'
            },
            {
                'title': 'Arrival Schedules',
                'description': 'Track incoming shipments and schedule warehouse receipts.',
                'url': 'procurement:arrival-list',
                'icon_name': 'truck',
                'badge': 'Arrivals'
            },
            {
                'title': 'Product Catalog',
                'description': 'View item specifications and media (Read-Only).',
                'url': 'catalog:catalog-overview',
                'icon_name': 'search',
                'badge': 'Reference'
            },
            {
                'title': 'Partner Database',
                'description': 'Manage your suppliers and customer network.',
                'url': 'partners:partner-list',
                'icon_name': 'users',
                'badge': 'Network'
            },
        ]
        return context

    def get_stock_controller_context(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Stock Controller Command Center"
        context['modules'] = [
            {
                'title': 'Procurement Operations',
                'description': 'Manage purchase orders, supplier deliveries, and warehouse receiving.',
                'url': 'procurement:overview',
                'icon_name': 'shopping-cart',
                'badge': 'Procurement'
            },
            {
                'title': 'Material Shortages',
                'description': 'View active material shortage gaps created from customer sales orders.',
                'url': 'procurement:shortage-list',
                'icon_name': 'alert-triangle',
                'badge': 'Shortages'
            },
            {
                'title': 'Product Catalog',
                'description': 'View item specifications and media (Read-Only).',
                'url': 'catalog:catalog-overview',
                'icon_name': 'box',
                'badge': 'Catalog'
            },
            {
                'title': 'Partner Database',
                'description': 'Track your global suppliers and customer network.',
                'url': 'partners:partner-list',
                'icon_name': 'users',
                'badge': 'Partners'
            },
            {
                'title': 'Stock Balance',
                'description': 'View current stock levels and warehouse distribution.',
                'url': 'inventory:stock-balance-list',
                'icon_name': 'database',
                'badge': 'Inventory'
            },
        ]
        return context

    def get_sales_context(self, **kwargs):
        from sales.models import SalesOrder, SalesOrderItem
        from django.db.models import Sum, F
        
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Sales Command Center"
        
        active_orders = SalesOrder.objects.filter(is_deleted=False)
        total_revenue = SalesOrderItem.objects.filter(
            order__is_deleted=False
        ).aggregate(
            total=Sum(F('requested_qty') * F('unit_price'))
        )['total'] or 0
        
        context['stats'] = {
            'confirmed_count': active_orders.filter(status=SalesOrder.Status.CONFIRMED).count(),
            'preorder_count': active_orders.filter(status=SalesOrder.Status.PREORDER).count(),
            'draft_count': active_orders.filter(status=SalesOrder.Status.DRAFT).count(),
            'total_revenue': total_revenue,
        }
        
        context['modules'] = [
            {
                'title': 'Sales Orders',
                'description': 'Manage sales orders, customer demands, and stock allocations.',
                'url': 'sales:overview',
                'icon_name': 'shopping-bag',
                'badge': 'Sells'
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
                'title': 'Product Catalog',
                'description': 'View item specifications and media (Read-Only).',
                'url': 'catalog:catalog-overview',
                'icon_name': 'box',
                'badge': 'Reference'
            },
            {
                'title': 'Partner Database',
                'description': 'Track and view your supplier and customer network.',
                'url': 'partners:partner-list',
                'icon_name': 'users',
                'badge': 'Partners'
            },
        ]
        return context
