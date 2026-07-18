from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.urls import reverse_lazy
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from accounting.models import PettyCashAccount
from accounting.forms.account_form import PettyCashAccountForm
from accounting.services.account_service import PettyCashAccountService


class PettyCashAccountListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PettyCashAccount
    template_name = 'accounting/account_list.html'
    context_object_name = 'accounts'
    permission_required = 'accounting.view_pettycashaccount'

    def get_queryset(self):
        qs = PettyCashAccount.objects.filter(is_deleted=False)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(code__icontains=q) | qs.filter(name__icontains=q) | qs.filter(custodian__username__icontains=q)
        return qs.select_related('company', 'custodian')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q', '')
        return context


class PettyCashAccountDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PettyCashAccount
    template_name = 'accounting/account_detail.html'
    context_object_name = 'account'
    permission_required = 'accounting.view_pettycashaccount'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['payments'] = self.object.payments.filter(is_deleted=False).order_by('-created_at')[:10]
        return context


class PettyCashAccountCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PettyCashAccount
    form_class = PettyCashAccountForm
    template_name = 'accounting/account_form.html'
    success_url = reverse_lazy('accounting:account-list')
    permission_required = 'accounting.add_pettycashaccount'

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        try:
            PettyCashAccountService.create_account(
                code=form.cleaned_data['code'],
                name=form.cleaned_data['name'],
                max_limit=form.cleaned_data['max_limit'],
                balance=form.cleaned_data['balance'],
                currency=form.cleaned_data['currency'],
                company=form.cleaned_data['company'],
                custodian=form.cleaned_data['custodian'],
                created_by=self.request.user,
                status=form.cleaned_data.get('status', 'active'),
                note=form.cleaned_data.get('note', '')
            )
            messages.success(self.request, "Petty cash account created successfully.")
            return redirect(self.success_url)
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)


class PettyCashAccountUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PettyCashAccount
    form_class = PettyCashAccountForm
    template_name = 'accounting/account_form.html'
    success_url = reverse_lazy('accounting:account-list')
    permission_required = 'accounting.change_pettycashaccount'

    def get_queryset(self):
        return PettyCashAccount.objects.filter(is_deleted=False)

    def form_valid(self, form):
        try:
            PettyCashAccountService.update_account(
                self.object,
                updated_by=self.request.user,
                code=form.cleaned_data['code'],
                name=form.cleaned_data['name'],
                max_limit=form.cleaned_data['max_limit'],
                status=form.cleaned_data['status'],
                note=form.cleaned_data['note']
            )
            messages.success(self.request, "Petty cash account updated successfully.")
            return redirect(self.success_url)
        except ValidationError as e:
            form.add_error(None, e)
            return self.form_invalid(form)


class PettyCashAccountDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = PettyCashAccount
    template_name = 'accounting/account_confirm_delete.html'
    success_url = reverse_lazy('accounting:account-list')
    permission_required = 'accounting.delete_pettycashaccount'

    def get_queryset(self):
        return PettyCashAccount.objects.filter(is_deleted=False)

    def form_valid(self, form):
        try:
            PettyCashAccountService.soft_delete_account(self.object, user=self.request.user)
            messages.success(self.request, "Petty cash account soft-deleted successfully.")
            return redirect(self.success_url)
        except ValidationError as e:
            messages.error(self.request, e.message)
            return redirect('accounting:account-detail', pk=self.object.pk)


class PettyCashAccountTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PettyCashAccount
    template_name = 'accounting/account_trash_list.html'
    context_object_name = 'accounts'
    permission_required = 'accounting.delete_pettycashaccount'

    def get_queryset(self):
        return PettyCashAccount.objects.filter(is_deleted=True).select_related('company', 'custodian')


class PettyCashAccountRestoreView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'accounting.delete_pettycashaccount'

    def post(self, request, pk, *args, **kwargs):
        account = get_object_or_404(PettyCashAccount, pk=pk, is_deleted=True)
        PettyCashAccountService.restore_account(account, user=request.user)
        messages.success(request, "Petty cash account restored successfully.")
        return redirect('accounting:account-list')
