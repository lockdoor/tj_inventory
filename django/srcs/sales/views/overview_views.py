from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Sum, F
from sales.models import SalesOrder, SalesOrderItem


class SalesOverviewView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Main overview page for the Sales module.
    Displays metrics dashboard and main navigation cards.
    """
    template_name = 'sales/overview.html'
    permission_required = 'sales.view_salesorder'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Sales Overview"
        
        # Query active (non-soft-deleted) sales orders
        active_orders = SalesOrder.objects.filter(is_deleted=False)
        
        # Calculate summary statistics
        context['confirmed_count'] = active_orders.filter(status=SalesOrder.Status.CONFIRMED).count()
        context['preorder_count'] = active_orders.filter(status=SalesOrder.Status.PREORDER).count()
        context['draft_count'] = active_orders.filter(status=SalesOrder.Status.DRAFT).count()
        
        # Revenue aggregation (sum of requested_qty * unit_price across active items of active orders)
        revenue = SalesOrderItem.objects.filter(
            order__is_deleted=False
        ).aggregate(
            total=Sum(F('requested_qty') * F('unit_price'))
        )['total'] or 0
        
        context['total_revenue'] = revenue
        return context
