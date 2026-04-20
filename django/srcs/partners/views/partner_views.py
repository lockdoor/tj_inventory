from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError

from partners.models import Partner
from partners.forms.partner_form import PartnerForm
from partners.services.partner_service import PartnerService

class PartnerListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for all active partners.
    Supports filtering by role (Supplier/Customer).
    """
    model = Partner
    template_name = 'partners/partner_list.html'
    context_object_name = 'partners'
    permission_required = 'partners.view_partner'
    raise_exception = True

    def get_queryset(self):
        queryset = PartnerService.get_active_queryset()
        
        role = self.request.GET.get('role')
        if role == 'supplier':
            queryset = queryset.filter(is_supplier=True)
        elif role == 'customer':
            queryset = queryset.filter(is_customer=True)
            
        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_role'] = self.request.GET.get('role', 'all')
        return context

class PartnerTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for soft-deleted partners (Trash).
    """
    model = Partner
    template_name = 'partners/partner_trash_list.html'
    context_object_name = 'partners'
    permission_required = 'partners.delete_partner'
    raise_exception = True

    def get_queryset(self):
        return PartnerService.list_deleted()

class PartnerDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed view for a single partner.
    """
    model = Partner
    template_name = 'partners/partner_detail.html'
    context_object_name = 'partner'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'partners.view_partner'
    raise_exception = True

    def get_queryset(self):
        # Only active partners in main detail view
        return PartnerService.get_active_queryset()

class PartnerCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    View for creating a new Partner.
    """
    model = Partner
    form_class = PartnerForm
    template_name = 'partners/partner_form.html'
    permission_required = 'partners.add_partner'
    raise_exception = True
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "New Partner"
        context['action_label'] = "Create Partner"
        return context

    def form_valid(self, form):
        try:
            partner = PartnerService.create(
                user=self.request.user,
                **form.cleaned_data
            )
            messages.success(self.request, f"Partner '{partner.name}' created successfully!")
            return redirect('partners:partner-list')
        except Exception as e:
            messages.error(self.request, f"Error creating partner: {str(e)}")
            return self.form_invalid(form)

class PartnerUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    View for updating an existing Partner.
    """
    model = Partner
    form_class = PartnerForm
    template_name = 'partners/partner_form.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'partners.change_partner'
    raise_exception = True

    def get_queryset(self):
        return PartnerService.get_active_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Partner: {self.object.name}"
        context['action_label'] = "Update Partner"
        return context

    def form_valid(self, form):
        try:
            PartnerService.update(
                self.object,
                user=self.request.user,
                **form.cleaned_data
            )
            messages.success(self.request, f"Partner '{self.object.name}' updated successfully!")
            return redirect('partners:partner-detail', code=self.object.code)
        except Exception as e:
            messages.error(self.request, f"Error updating partner: {str(e)}")
            return self.form_invalid(form)

class PartnerDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    View for soft-deleting a Partner.
    """
    model = Partner
    template_name = 'partners/partner_confirm_delete.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'partners.delete_partner'
    success_url = reverse_lazy('partners:partner-list')
    raise_exception = True

    def get_queryset(self):
        return PartnerService.get_active_queryset()

    def form_valid(self, form):
        try:
            PartnerService.soft_delete(self.get_object(), user=self.request.user)
            messages.success(self.request, f"Partner '{self.object.name}' moved to trash.")
            return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f"Unexpected error: {str(e)}")
            return self.get(self.request)

class PartnerRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view for restoring a soft-deleted Partner.
    """
    permission_required = 'partners.delete_partner'
    raise_exception = True

    def post(self, request, code):
        partner = get_object_or_404(Partner, code=code, is_deleted=True)
        try:
            PartnerService.restore(partner, user=request.user)
            messages.success(request, f"Partner '{partner.name}' restored successfully.")
            return redirect('partners:partner-list')
        except Exception as e:
            messages.error(request, f"Unexpected error while restoring: {str(e)}")
            return redirect('partners:partner-trash')
