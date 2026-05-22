from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Sum, F, Q
from sales.models import SalesOrder, SalesOrderItem
from sales.services.sales_service import SalesService

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


class SalesOrderListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Paginated search-enabled table listing active sales orders.
    """
    model = SalesOrder
    template_name = 'sales/sales_order_list.html'
    context_object_name = 'sales_orders'
    permission_required = 'sales.view_salesorder'
    raise_exception = True
    paginate_by = 10

    def get_queryset(self):
        # Retrieve active non-deleted queryset, ordered newest first
        queryset = SalesService.get_active_queryset().order_by('-order_date', '-created_at')
        
        q = self.request.GET.get('q')
        if q:
            q = q.strip()
            queryset = queryset.filter(
                Q(document_no__icontains=q) |
                Q(partner__name__icontains=q)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Sales Orders"
        context['q'] = self.request.GET.get('q', '')
        return context
