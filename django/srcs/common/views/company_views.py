from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views import View
from django.views.generic import ListView, DetailView, UpdateView, CreateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.core.exceptions import ValidationError

from common.models import Company
from common.forms.company_form import CompanyForm
from common.services.company_service import CompanyService


class CompanyListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for all active companies.
    """
    model = Company
    template_name = 'common/company_list.html'
    context_object_name = 'companies'
    permission_required = 'common.view_company'
    raise_exception = True

    def get_queryset(self):
        return CompanyService.list_active()


class CompanyTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    """
    List view for soft-deleted companies (Trash).
    """
    model = Company
    template_name = 'common/company_trash_list.html'
    context_object_name = 'companies'
    permission_required = 'common.delete_company'
    raise_exception = True

    def get_queryset(self):
        return CompanyService.list_deleted()


class CompanyDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    """
    Detailed view for a single company.
    """
    model = Company
    template_name = 'common/company_detail.html'
    context_object_name = 'company'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'common.view_company'
    raise_exception = True

    def get_queryset(self):
        return CompanyService.get_active_queryset()


class CompanyCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    """
    View for creating a new Company.
    """
    model = Company
    form_class = CompanyForm
    template_name = 'common/company_form.html'
    permission_required = 'common.add_company'
    raise_exception = True
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "New Company"
        context['action_label'] = "Create Company"
        return context

    def form_valid(self, form):
        try:
            company = CompanyService.create(
                user=self.request.user,
                **form.cleaned_data
            )
            messages.success(self.request, f"Company '{company.name}' created successfully!")
            return redirect('common:company-list')
        except Exception as e:
            messages.error(self.request, f"Error creating company: {str(e)}")
            return self.form_invalid(form)


class CompanyUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    """
    View for updating an existing Company.
    """
    model = Company
    form_class = CompanyForm
    template_name = 'common/company_form.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'common.change_company'
    raise_exception = True

    def get_queryset(self):
        return CompanyService.get_active_queryset()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f"Update Company: {self.object.name}"
        context['action_label'] = "Update Company"
        return context

    def form_valid(self, form):
        try:
            CompanyService.update(
                self.object,
                user=self.request.user,
                **form.cleaned_data
            )
            messages.success(self.request, f"Company '{self.object.name}' updated successfully!")
            return redirect('common:company-detail', code=self.object.code)
        except Exception as e:
            messages.error(self.request, f"Error updating company: {str(e)}")
            return self.form_invalid(form)


class CompanyDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    """
    View for soft-deleting a Company.
    """
    model = Company
    template_name = 'common/company_confirm_delete.html'
    slug_field = 'code'
    slug_url_kwarg = 'code'
    permission_required = 'common.delete_company'
    success_url = reverse_lazy('common:company-list')
    raise_exception = True

    def get_queryset(self):
        return CompanyService.get_active_queryset()

    def form_valid(self, form):
        try:
            CompanyService.soft_delete(self.get_object(), user=self.request.user)
            messages.success(self.request, f"Company '{self.object.name}' moved to trash.")
            return redirect(self.success_url)
        except Exception as e:
            messages.error(self.request, f"Unexpected error: {str(e)}")
            return self.get(self.request)


class CompanyRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view for restoring a soft-deleted Company.
    """
    permission_required = 'common.delete_company'
    raise_exception = True

    def post(self, request, code):
        company = get_object_or_404(Company, code=code, is_deleted=True)
        try:
            CompanyService.restore(company, user=request.user)
            messages.success(request, f"Company '{company.name}' restored successfully.")
            return redirect('common:company-list')
        except Exception as e:
            messages.error(request, f"Unexpected error while restoring: {str(e)}")
            return redirect('common:company-trash')
