from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError

from ..models import Arrival, PurchaseOrder
from ..forms import ArrivalForm, ArrivalItemFormSet
from ..services.arrival_service import ArrivalService


class ArrivalListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Arrival
    template_name = 'procurement/arrival_list.html'
    context_object_name = 'arrivals'
    permission_required = 'procurement.view_arrival'
    paginate_by = 10

    def get_queryset(self):
        return ArrivalService.get_active_queryset().order_by('-expected_date', '-created_at')


class ArrivalCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Arrival
    form_class = ArrivalForm
    template_name = 'procurement/arrival_form.html'
    permission_required = 'procurement.add_arrival'
    success_url = reverse_lazy('procurement:arrival-list')

    def get_initial(self):
        initial = super().get_initial()
        # Pre-fill from GET parameters (e.g. from Purchase Order)
        for field in ['purchase_order', 'partner', 'document_no', 'expected_date']:
            if self.request.GET.get(field):
                initial[field] = self.request.GET.get(field)
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = ArrivalItemFormSet(self.request.POST)
        else:
            context['items'] = ArrivalItemFormSet()
        return context

    def form_valid(self, form):
        items = ArrivalItemFormSet(self.request.POST)
        if items.is_valid():
            try:
                with transaction.atomic():
                    header_data = form.cleaned_data
                    items_data = []
                    for item_form in items:
                        if item_form.cleaned_data and not item_form.cleaned_data.get('DELETE', False):
                            items_data.append(item_form.cleaned_data)
                    
                    self.object = ArrivalService.create(
                        document_no=header_data['document_no'],
                        partner=header_data['partner'],
                        warehouse=header_data['warehouse'],
                        expected_date=header_data['expected_date'],
                        user=self.request.user,
                        purchase_order=header_data.get('purchase_order'),
                        note=header_data.get('note', ''),
                        items=items_data
                    )
                messages.success(self.request, f"Arrival schedule {self.object.document_no} created.")
                return redirect('procurement:arrival-detail', pk=self.object.pk)
            except ValidationError as e:
                form.add_error(None, e)
                return self.form_invalid(form)
        return self.form_invalid(form)


class ArrivalUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Arrival
    form_class = ArrivalForm
    template_name = 'procurement/arrival_form.html'
    permission_required = 'procurement.change_arrival'

    def get_queryset(self):
        return ArrivalService.get_active_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['items'] = ArrivalItemFormSet(self.request.POST, instance=self.object)
        else:
            context['items'] = ArrivalItemFormSet(instance=self.object)
        return context

    def form_valid(self, form):
        items = ArrivalItemFormSet(self.request.POST, instance=self.object)
        if items.is_valid():
            try:
                header_data = form.cleaned_data
                items_data = []
                for item_form in items:
                    data = item_form.cleaned_data
                    if item_form.instance.pk:
                        data['id'] = item_form.instance.pk
                    items_data.append(data)

                ArrivalService.update(
                    self.object,
                    user=self.request.user,
                    items_data=items_data,
                    **header_data
                )
                messages.success(self.request, f"Arrival {self.object.document_no} updated.")
                return redirect('procurement:arrival-detail', pk=self.object.pk)
            except ValidationError as e:
                form.add_error(None, e)
                return self.form_invalid(form)
        return self.form_invalid(form)


class ArrivalDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Arrival
    template_name = 'procurement/arrival_detail.html'
    context_object_name = 'arrival'
    permission_required = 'procurement.view_arrival'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.all().select_related('item', 'po_item')
        
        # Attachments
        context['attachments'] = self.object.attachments.filter(is_deleted=False)
        from ..forms import ArrivalAttachmentForm
        context['attachment_form'] = ArrivalAttachmentForm()
        
        # Linked Inventory Movement (if any)
        from inventory.models import InventoryMovement
        context['movements'] = InventoryMovement.objects.filter(
            reference_type=InventoryMovement.ReferenceType.STOCK_ARRIVAL,
            reference_no=self.object.document_no,
            is_deleted=False
        )
        
        # Enforce that only warehouse_admin can receive
        context['is_warehouse_admin'] = self.request.user.is_superuser or self.request.user.groups.filter(name='warehouse_admin').exists()

        # Context for Stock Controller
        if self.request.user.is_superuser or self.request.user.groups.filter(name='stock_controller').exists():
            context['is_stock_controller'] = True
        
        return context


class ArrivalFromPOView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Redirects to the Arrival Create page with pre-filled data from a PO.
    """
    permission_required = 'procurement.add_arrival'

    def get(self, request, po_pk):
        po = get_object_or_404(PurchaseOrder, pk=po_pk)
        
        # Check if PO is submitted
        if po.status != PurchaseOrder.Status.SUBMITTED:
             messages.error(request, "Arrivals can only be scheduled for SUBMITTED Purchase Orders.")
             return redirect('procurement:purchase-order-detail', pk=po.pk)

        # Generate a suggested doc number
        last_arrival = Arrival.objects.all().order_by('id').last()
        new_id = (last_arrival.id + 1) if last_arrival else 1
        suggested_no = f"ARR-{po.document_no}-{new_id:03d}"

        # We redirect to the create view with initial data in the session or GET params?
        # GET params are simpler for many fields.
        params = f"?purchase_order={po.pk}&partner={po.partner.pk}&document_no={suggested_no}"
        if po.expected_date:
            params += f"&expected_date={po.expected_date.isoformat()}"
            
        return redirect(reverse('procurement:arrival-create') + params)


class ArrivalReceiveActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Triggers the generation of an Inventory Movement for receiving.
    """
    permission_required = 'procurement.change_arrival'

    def post(self, request, pk):
        import decimal
        arrival = get_object_or_404(Arrival, pk=pk)
        
        # Only warehouse admin can start receiving
        is_wh_admin = request.user.is_superuser or request.user.groups.filter(name='warehouse_admin').exists()
        if not is_wh_admin:
            messages.error(request, "Only a Warehouse Admin can start the receiving process.")
            return redirect('procurement:arrival-detail', pk=arrival.pk)
        
        receive_quantities = {}
        for key, value in request.POST.items():
            if key.startswith('qty_'):
                try:
                    item_id = int(key.replace('qty_', ''))
                    receive_quantities[item_id] = decimal.Decimal(value)
                except (ValueError, decimal.InvalidOperation):
                    pass

        try:
            movement = ArrivalService.initiate_receiving(arrival, request.user, receive_quantities=receive_quantities)
            messages.success(request, f"Receiving process started. Inventory Movement {movement.document_no} created.")
            return redirect('inventory:movement-detail', pk=movement.pk)
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('procurement:arrival-detail', pk=arrival.pk)


class ArrivalCancelReceiveActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Cancels the receiving process and reverts Arrival back to SCHEDULED.
    """
    permission_required = 'procurement.change_arrival'

    def post(self, request, pk):
        arrival = get_object_or_404(Arrival, pk=pk)
        try:
            ArrivalService.cancel_receiving(arrival, request.user)
            messages.success(request, f"Receiving cancelled for Arrival {arrival.document_no}. Reverted to Scheduled.")
        except ValidationError as e:
            messages.error(request, str(e))
        return redirect('procurement:arrival-detail', pk=arrival.pk)

class ArrivalDeleteActionView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Deletes an Arrival if no active movements reference it.
    """
    permission_required = 'procurement.delete_arrival'

    def post(self, request, pk):
        arrival = get_object_or_404(Arrival, pk=pk, is_deleted=False)
        try:
            ArrivalService.delete(arrival, user=request.user)
            messages.success(request, f"Arrival {arrival.document_no} successfully deleted.")
            return redirect('procurement:arrival-list')
        except ValidationError as e:
            messages.error(request, str(e))
            return redirect('procurement:arrival-detail', pk=arrival.pk)
