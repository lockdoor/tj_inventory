from django.views.generic import ListView, CreateView, DetailView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.shortcuts import get_object_or_404, redirect

from procurement.models import ArrivalReservation
from procurement.forms import ArrivalReservationForm
from procurement.services import ArrivalReservationService

class ArrivalReservationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List of active expected arrival reservations.
    Allows procurement planners and warehouse admins to view pre-allocations.
    """
    model = ArrivalReservation
    template_name = 'procurement/reservation_list.html'
    context_object_name = 'reservations'
    permission_required = 'procurement.view_arrival'
    paginate_by = 15

    def get_queryset(self):
        """
        Optimize DB queries using select_related and Q searches.
        """
        queryset = ArrivalReservation.objects.filter(is_deleted=False).select_related(
            'arrival_item__arrival',
            'arrival_item__item',
            'arrival_item__arrival__partner',
            'sales_item__order',
            'created_by'
        ).order_by('-created_at')

        q = self.request.GET.get('q')
        if q:
            q = q.strip()
            queryset = queryset.filter(
                Q(reference_no__icontains=q) |
                Q(arrival_item__arrival__document_no__icontains=q) |
                Q(arrival_item__item__name__icontains=q) |
                Q(arrival_item__item__sku__icontains=q) |
                Q(note__icontains=q)
            )

        return queryset

    def get_context_data(self, **kwargs):
        """
        Add pagination and roles metadata.
        """
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Arrival Reservations"
        context['q'] = self.request.GET.get('q', '')
        groups = self.request.user.groups.values_list('name', flat=True)
        context['is_executive'] = 'executive' in groups or self.request.user.is_superuser
        return context


class ArrivalReservationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    Create a new dynamic arrival expected reservation.
    """
    model = ArrivalReservation
    form_class = ArrivalReservationForm
    template_name = 'procurement/reservation_form.html'
    success_url = reverse_lazy('procurement:arrival-reservation-list')
    permission_required = 'procurement.view_arrival'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Create Arrival Reservation"
        return context

    def form_valid(self, form):
        try:
            self.object = ArrivalReservationService.reserve_future(
                arrival_item=form.cleaned_data['arrival_item'],
                quantity=form.cleaned_data['quantity'],
                reference_no=form.cleaned_data['reference_no'],
                reference_type=form.cleaned_data['reference_type'],
                note=form.cleaned_data['note'],
                created_by=self.request.user
            )
            messages.success(self.request, "Arrival reservation created successfully.")
            return HttpResponseRedirect(self.get_success_url())

        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)


class ArrivalReservationDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed expected arrival pre-allocation holding view.
    """
    model = ArrivalReservation
    template_name = 'procurement/reservation_detail.html'
    context_object_name = 'reservation'
    permission_required = 'procurement.view_arrival'

    def get_queryset(self):
        return ArrivalReservation.objects.filter(is_deleted=False).select_related(
            'arrival_item__arrival',
            'arrival_item__item',
            'arrival_item__arrival__partner',
            'arrival_item__arrival__warehouse',
            'sales_item__order',
            'created_by'
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Arrival Reservation: {self.object.reference_no}"
        groups = self.request.user.groups.values_list('name', flat=True)
        context['is_executive'] = 'executive' in groups or self.request.user.is_superuser
        return context


class ArrivalReservationReleaseView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    Release/unlock an existing arrival expected reservation.
    """
    permission_required = 'procurement.view_arrival'
    raise_exception = True

    def post(self, request, *args, **kwargs):
        reservation = get_object_or_404(ArrivalReservation, pk=self.kwargs.get('pk'))
        
        # Access control: only creator or an executive/superuser can release.
        is_creator = reservation.created_by == request.user
        is_executive = request.user.is_superuser or request.user.groups.filter(name='executive').exists()
        if not (is_creator or is_executive):
            raise PermissionDenied("Only the creator of the reservation or an executive can release this lock.")

        reference_no = reservation.reference_no
        ArrivalReservationService.release(reservation)
        messages.success(request, f"Arrival Reservation {reference_no} has been successfully released.")
        return redirect('procurement:arrival-reservation-list')
