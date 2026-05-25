from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q, Sum
from django.urls import reverse_lazy
from django.contrib import messages
from django.shortcuts import redirect, get_object_or_404
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


class ShortageDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed view for a single shortage record showing full item context,
    audit trail, linked PO, status actions, and internal notes.
    """
    model = Shortage
    template_name = 'procurement/shortage_detail.html'
    context_object_name = 'shortage'
    permission_required = 'procurement.view_purchaseorder'
    raise_exception = True

    def get_queryset(self):
        return Shortage.objects.filter(is_deleted=False).select_related(
            'item',
            'purchase_order',
            'created_by',
            'updated_by'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        shortage = self.object
        context['page_title'] = f"Shortage: {shortage.item.sku}"

        # Determine if the current user can perform cancel action
        user = self.request.user
        is_creator = shortage.created_by == user
        is_executive = user.groups.filter(name='executive').exists()
        context['can_cancel'] = (
            shortage.status == Shortage.Status.PENDING
            and (is_creator or is_executive or user.is_superuser)
        )
        context['is_executive'] = is_executive

        # Collect current item stock summary for diagnostics
        stocks = shortage.item.stocks.filter(
            is_deleted=False
        ).exclude(balance=0).select_related('warehouse')
        context['item_stocks'] = stocks
        context['total_stock_qty'] = sum(s.balance for s in stocks)

        return context


class ShortageCancelView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    POST-only action to cancel a pending shortage record.
    """
    model = Shortage
    permission_required = 'procurement.view_purchaseorder'
    raise_exception = True
    http_method_names = ['post']

    def get_queryset(self):
        return Shortage.objects.filter(is_deleted=False)

    def post(self, request, *args, **kwargs):
        shortage = self.get_object()
        user = request.user

        # Gate: only pending shortages can be cancelled
        if shortage.status != Shortage.Status.PENDING:
            messages.error(request, "Only pending shortages can be cancelled.")
            return redirect('procurement:shortage-detail', pk=shortage.pk)

        # Gate: only creator, executive, or superuser
        is_creator = shortage.created_by == user
        is_executive = user.groups.filter(name='executive').exists()
        if not (is_creator or is_executive or user.is_superuser):
            messages.error(request, "You do not have permission to cancel this shortage.")
            return redirect('procurement:shortage-detail', pk=shortage.pk)

        shortage.status = Shortage.Status.CANCELLED
        shortage.updated_by = user
        shortage.save()
        messages.success(request, f"Shortage for {shortage.item.sku} has been cancelled.")
        return redirect('procurement:shortage-detail', pk=shortage.pk)


class ShortageCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Manually record an item shortage.
    """
    model = Shortage
    form_class = ShortageForm
    template_name = 'procurement/shortage_form.html'
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

    def get_success_url(self):
        return reverse_lazy('procurement:shortage-detail', kwargs={'pk': self.object.pk})


class ShortageUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    Edit and update an existing material shortage.
    Only allowed for shortages in PENDING status.
    """
    model = Shortage
    form_class = ShortageForm
    template_name = 'procurement/shortage_form.html'
    permission_required = 'procurement.view_purchaseorder'
    raise_exception = True

    def get_queryset(self):
        return Shortage.objects.filter(is_deleted=False)

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj.status != Shortage.Status.PENDING:
            messages.error(request, "Only pending shortages can be edited.")
            return redirect('procurement:shortage-detail', pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Edit Material Shortage: {self.object.item.sku}"
        
        from catalog.models import Item, ItemPackaging
        context['items'] = Item.objects.filter(status='active', is_deleted=False).prefetch_related('stocks__warehouse').order_by('sku')
        context['packagings'] = ItemPackaging.objects.filter(status='active', is_deleted=False).select_related('item').order_by('name')
        
        return context

    def form_valid(self, form):
        from django.core.exceptions import ValidationError
        from procurement.services.shortage_service import ShortageService
        try:
            self.object = ShortageService.update(
                self.get_object(),
                user=self.request.user,
                item=form.cleaned_data.get('item'),
                request_qty=form.cleaned_data.get('request_qty'),
                expected_date=form.cleaned_data.get('expected_date'),
                reference_type=form.cleaned_data.get('reference_type'),
                reference_id=form.cleaned_data.get('reference_id'),
                note=form.cleaned_data.get('note')
            )
            messages.success(self.request, "Material shortage updated successfully.")
            return redirect('procurement:shortage-detail', pk=self.object.pk)
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

