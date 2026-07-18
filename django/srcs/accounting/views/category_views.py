from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from accounting.models import PettyCashCategory
from accounting.forms.category_form import PettyCashCategoryForm
from accounting.services.category_service import PettyCashCategoryService

from django.db.models import Count, Q
from common.models import Company
from accounting.services.express_service import ExpressService


class PettyCashCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PettyCashCategory
    template_name = 'accounting/category_list.html'
    context_object_name = 'categories'
    permission_required = 'accounting.view_pettycashcategory'

    def get_queryset(self):
        company_id = self.request.GET.get('company_id')
        if not company_id:
            return PettyCashCategory.objects.none()
        qs = PettyCashCategory.objects.filter(is_deleted=False, company_id=company_id)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(code__icontains=q) | qs.filter(name__icontains=q)
        return qs.select_related('company')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        company_id = self.request.GET.get('company_id')
        if company_id:
            context['selected_company'] = get_object_or_404(Company, pk=company_id, is_deleted=False)
        else:
            companies = Company.objects.filter(is_deleted=False).annotate(
                category_count=Count('expense_categories', filter=Q(expense_categories__is_deleted=False))
            )
            context['companies'] = companies
        context['q'] = self.request.GET.get('q', '')
        return context


class PettyCashCategorySyncView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'accounting.add_pettycashcategory'

    def post(self, request, company_id, *args, **kwargs):
        company = get_object_or_404(Company, pk=company_id, is_deleted=False)
        if not company.express_database_name:
            messages.error(request, f"Company '{company.code}' does not have an Express database name configured.")
            return redirect('accounting:category-list')
        try:
            ExpressService.update_category_from_express(company, request.user)
            messages.success(request, f"Successfully synced chart of accounts for '{company.code}' from Express!")
        except Exception as e:
            messages.error(request, f"Failed to sync from Express: {e}")
        return redirect(f"{reverse_lazy('accounting:category-list')}?company_id={company.pk}")


class PettyCashCategoryDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PettyCashCategory
    template_name = 'accounting/category_detail.html'
    context_object_name = 'category'
    permission_required = 'accounting.view_pettycashcategory'

    def get_queryset(self):
        return PettyCashCategory.objects.filter(is_deleted=False)


class PettyCashCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PettyCashCategory
    form_class = PettyCashCategoryForm
    template_name = 'accounting/category_form.html'
    success_url = reverse_lazy('accounting:category-list')
    permission_required = 'accounting.add_pettycashcategory'

    def form_valid(self, form):
        try:
            self.object = PettyCashCategoryService.create_category(
                code=form.cleaned_data['code'],
                name=form.cleaned_data['name'],
                company=form.cleaned_data['company'],
                created_by=self.request.user,
                note=form.cleaned_data.get('note', '')
            )
            messages.success(self.request, f"Category '{self.object.code}' created successfully.")
            return redirect(self.get_success_url())
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)


class PettyCashCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PettyCashCategory
    form_class = PettyCashCategoryForm
    template_name = 'accounting/category_form.html'
    permission_required = 'accounting.change_pettycashcategory'

    def get_queryset(self):
        return PettyCashCategory.objects.filter(is_deleted=False)

    def form_valid(self, form):
        try:
            self.object = PettyCashCategoryService.update_category(
                self.object,
                updated_by=self.request.user,
                code=form.cleaned_data['code'],
                name=form.cleaned_data['name'],
                note=form.cleaned_data.get('note', '')
            )
            messages.success(self.request, f"Category '{self.object.code}' updated successfully.")
            return redirect(self.get_success_url())
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse_lazy('accounting:category-detail', kwargs={'pk': self.object.pk})


class PettyCashCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = PettyCashCategory
    template_name = 'accounting/category_confirm_delete.html'
    success_url = reverse_lazy('accounting:category-list')
    permission_required = 'accounting.delete_pettycashcategory'

    def get_queryset(self):
        return PettyCashCategory.objects.filter(is_deleted=False)

    def form_valid(self, form):
        try:
            PettyCashCategoryService.soft_delete_category(self.get_object(), user=self.request.user)
            messages.success(self.request, "Category deleted successfully.")
            return redirect(self.get_success_url())
        except ValidationError as e:
            messages.error(self.request, str(e))
            return redirect('accounting:category-detail', pk=self.get_object().pk)


class PettyCashCategoryTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PettyCashCategory
    template_name = 'accounting/category_trash_list.html'
    context_object_name = 'categories'
    permission_required = 'accounting.delete_pettycashcategory'

    def get_queryset(self):
        return PettyCashCategory.objects.filter(is_deleted=True).select_related('company')


class PettyCashCategoryRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'accounting.delete_pettycashcategory'

    def post(self, request, pk, *args, **kwargs):
        category = get_object_or_404(PettyCashCategory, pk=pk, is_deleted=True)
        PettyCashCategoryService.restore_category(category, user=request.user)
        messages.success(request, f"Category '{category.code}' restored successfully.")
        return redirect('accounting:category-list')
