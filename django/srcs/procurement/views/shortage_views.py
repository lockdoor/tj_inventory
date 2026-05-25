from django.views.generic import ListView, CreateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum
from django.urls import reverse_lazy
from django.contrib import messages
from procurement.models import Shortage
from procurement.forms import ShortageForm

class ShortageListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    Search-enabled, paginated list of material shortages.
    Allows stock controllers to monitor allocation gaps and decide PO quantities.
    """
    model = Shortage
    template_name = 'procurement/shortage_list.html'
    context_object_name = 'shortages'
    permission_required = 'procurement.view_purchaseorder'
    raise_exception = True
    paginate_by = 15

    def get_queryset(self):
        queryset = Shortage.objects.filter(is_deleted=False).select_related(
            'item',
            'purchase_order',
            'created_by'
        ).order_by('-created_at')

        # Status filter
        status = self.request.GET.get('status')
        if status and status in dict(Shortage.Status.choices):
            queryset = queryset.filter(status=status)

        # Search query
        q = self.request.GET.get('q')
        if q:
            q = q.strip()
            queryset = queryset.filter(
                Q(reference_id__icontains=q) |
                Q(item__name__icontains=q) |
                Q(item__sku__icontains=q) |
                Q(note__icontains=q)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Material Shortages"
        context['q'] = self.request.GET.get('q', '')
        context['current_status'] = self.request.GET.get('status', 'all')
        
        # Calculate dynamic KPIs
        all_active = Shortage.objects.filter(is_deleted=False)
        context['pending_count'] = all_active.filter(status=Shortage.Status.PENDING).count()
        context['po_created_count'] = all_active.filter(status=Shortage.Status.PO_CREATED).count()
        
        total_pending_qty = all_active.filter(
            status=Shortage.Status.PENDING
        ).aggregate(total=Sum('request_qty'))['total'] or 0
        context['total_pending_qty'] = float(total_pending_qty)
        
        unique_short_items = all_active.filter(
            status=Shortage.Status.PENDING
        ).values('item').distinct().count()
        context['unique_short_items'] = unique_short_items

        return context


class ShortageCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Manually record an item shortage.
    """
    model = Shortage
    form_class = ShortageForm
    template_name = 'procurement/shortage_form.html'
    success_url = reverse_lazy('procurement:shortage-list')
    permission_required = 'procurement.view_purchaseorder'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Record Material Shortage"
        
        from catalog.models import Item, ItemPackaging
        context['items'] = Item.objects.filter(status='active', is_deleted=False).prefetch_related('stocks__warehouse').order_by('sku')
        context['packagings'] = ItemPackaging.objects.filter(status='active', is_deleted=False).select_related('item').order_by('name')
        
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.status = Shortage.Status.PENDING
        messages.success(self.request, "Material shortage recorded successfully.")
        return super().form_valid(form)
