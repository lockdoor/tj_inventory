from django.views.generic import ListView, CreateView, DetailView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404, redirect

from inventory.models import StockReservation
from inventory.forms import StockReservationForm
from inventory.services import ReservationService

class StockReservationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List of active physical stock reservations.
    Allows warehouse admins and stock controllers to view which physical lots are locked.
    """
    model = StockReservation
    template_name = 'inventory/reservation_list.html'
    context_object_name = 'reservations'
    permission_required = 'inventory.view_stock'
    raise_exception = True
    paginate_by = 15

    def get_queryset(self):
        """
        Optimize database retrieval with select_related and support search query.
        """
        queryset = StockReservation.objects.select_related(
            'stock__item',
            'stock__warehouse',
            'sales_item__order'
        ).all().order_by('-created_at')

        q = self.request.GET.get('q')
        if q:
            q = q.strip()
            queryset = queryset.filter(
                Q(reference_no__icontains=q) |
                Q(stock__lot_number__icontains=q) |
                Q(stock__item__name__icontains=q) |
                Q(stock__item__sku__icontains=q) |
                Q(note__icontains=q)
            )

        return queryset

    def get_context_data(self, **kwargs):
        """
        Add extra context such as page title and current search query.
        """
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Stock Reservations"
        context['q'] = self.request.GET.get('q', '')
        groups = self.request.user.groups.values_list('name', flat=True)
        context['is_executive'] = 'executive' in groups or self.request.user.is_superuser
        return context


class StockReservationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create a new physical stock reservation.
    """
    model = StockReservation
    form_class = StockReservationForm
    template_name = 'inventory/reservation_form.html'
    success_url = reverse_lazy('inventory:reservation-list')
    permission_required = 'inventory.view_stock'
    raise_exception = True

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Create Stock Reservation"
        return context

    def form_valid(self, form):
        try:
            self.object = ReservationService.reserve(
                stock=form.cleaned_data['stock'],
                quantity=form.cleaned_data['quantity'],
                reference_no=form.cleaned_data['reference_no'],
                reference_type=form.cleaned_data['reference_type'],
                note=form.cleaned_data['note'],
                created_by=self.request.user
            )
            messages.success(self.request, "Stock reservation created successfully.")
            return HttpResponseRedirect(self.get_success_url())

        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)


class StockReservationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed physical stock reservation holding view.
    Includes metadata, locks, linked lots and notes.
    """
    model = StockReservation
    template_name = 'inventory/reservation_detail.html'
    context_object_name = 'reservation'
    permission_required = 'inventory.view_stock'
    raise_exception = True

    def get_queryset(self):
        return StockReservation.objects.select_related(
            'stock__item',
            'stock__warehouse',
            'sales_item__order',
            'created_by'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Reservation Detail: {self.object.reference_no}"
        groups = self.request.user.groups.values_list('name', flat=True)
        context['is_executive'] = 'executive' in groups or self.request.user.is_superuser
        return context


class StockReservationReleaseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Release/unlock an existing physical stock reservation.
    """
    permission_required = 'inventory.view_stock'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        reservation = get_object_or_404(StockReservation, pk=self.kwargs.get('pk'))
        
        # Access control: only creator or an executive/superuser can release.
        is_creator = reservation.created_by == request.user
        is_executive = request.user.is_superuser or request.user.groups.filter(name='executive').exists()
        if not (is_creator or is_executive):
            raise PermissionDenied("Only the creator of the reservation or an executive can release this lock.")

        reference_no = reservation.reference_no
        ReservationService.release(reservation)
        messages.success(request, f"Reservation {reference_no} has been successfully released.")
        return redirect('inventory:reservation-list')

