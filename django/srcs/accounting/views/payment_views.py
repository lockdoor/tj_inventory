import datetime
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.utils import timezone
from accounting.models import PettyCashPayment, PettyCashAccount, PettyCashPaymentItem
from accounting.forms.payment_form import PettyCashPaymentForm, PettyCashPaymentItemFormSet
from accounting.services.payment_service import PettyCashPaymentService


class PettyCashPaymentListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PettyCashPayment
    template_name = 'accounting/payment_list.html'
    context_object_name = 'payments'
    permission_required = 'accounting.view_pettycashpayment'
    paginate_by = 20

    def get_account(self):
        return get_object_or_404(PettyCashAccount, code=self.kwargs['account_code'], is_deleted=False)

    def get_queryset(self):
        account = self.get_account()
        qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(payment_no__icontains=q) | qs.filter(payee_name__icontains=q) | qs.filter(note__icontains=q)
        return qs.select_related('account', 'created_by').prefetch_related('items')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = self.get_account()
        context['q'] = self.request.GET.get('q', '')
        return context


class PettyCashPaymentDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = PettyCashPayment
    template_name = 'accounting/payment_detail.html'
    context_object_name = 'payment'
    permission_required = 'accounting.view_pettycashpayment'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.all().select_related('category')
        return context


class PettyCashPaymentCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = PettyCashPayment
    form_class = PettyCashPaymentForm
    template_name = 'accounting/payment_form.html'
    permission_required = 'accounting.add_pettycashpayment'

    def get_account(self):
        return get_object_or_404(PettyCashAccount, code=self.kwargs['account_code'], is_deleted=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.get_account()
        context['account'] = account
        if self.request.POST:
            context['formset'] = PettyCashPaymentItemFormSet(self.request.POST, company=account.company)
        else:
            context['formset'] = PettyCashPaymentItemFormSet(company=account.company)
        return context

    def form_valid(self, form):
        account = self.get_account()
        context = self.get_context_data()
        formset = context['formset']
        
        if formset.is_valid():
            items_data = []
            for item_form in formset:
                if item_form.cleaned_data.get('DELETE'):
                    continue
                if not item_form.cleaned_data.get('amount'):
                    continue
                items_data.append({
                    'category': item_form.cleaned_data.get('category'),
                    'description': item_form.cleaned_data.get('description', ''),
                    'amount': item_form.cleaned_data['amount'],
                    'tax': item_form.cleaned_data.get('tax'),
                    'note': item_form.cleaned_data.get('note', '')
                })

            try:
                PettyCashPaymentService.create_payment(
                    account=account,
                    payment_type=form.cleaned_data['payment_type'],
                    items_data=items_data,
                    payee=form.cleaned_data.get('payee'),
                    payee_name=form.cleaned_data.get('payee_name', ''),
                    payment_date=form.cleaned_data.get('payment_date'),
                    created_by=self.request.user,
                    note=form.cleaned_data.get('note', '')
                )
                messages.success(self.request, "Voucher created and balance updated successfully.")
                return redirect('accounting:payment-list', account_code=account.code)
            except ValidationError as e:
                form.add_error(None, e)
                return self.form_invalid(form)
        else:
            return self.form_invalid(form)


class PettyCashPaymentUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = PettyCashPayment
    form_class = PettyCashPaymentForm
    template_name = 'accounting/payment_form.html'
    permission_required = 'accounting.change_pettycashpayment'

    def get_queryset(self):
        return PettyCashPayment.objects.filter(is_deleted=False)

    def dispatch(self, request, *args, **kwargs):
        payment = self.get_object()
        if payment.is_posted:
            messages.error(request, "This payment is posted to Express and cannot be updated.")
            return redirect('accounting:payment-detail', pk=payment.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.object.account
        context['account'] = account
        if self.request.POST:
            context['formset'] = PettyCashPaymentItemFormSet(self.request.POST, instance=self.object, company=account.company)
        else:
            context['formset'] = PettyCashPaymentItemFormSet(instance=self.object, company=account.company)
        return context

    def form_valid(self, form):
        account = self.object.account
        context = self.get_context_data()
        formset = context['formset']
        
        if formset.is_valid():
            items_data = []
            for item_form in formset:
                if item_form.cleaned_data.get('DELETE'):
                    continue
                if not item_form.cleaned_data.get('amount'):
                    continue
                items_data.append({
                    'category': item_form.cleaned_data.get('category') or (item_form.instance.category if item_form.instance and item_form.instance.pk else None),
                    'description': item_form.cleaned_data.get('description', ''),
                    'amount': item_form.cleaned_data['amount'],
                    'tax': item_form.cleaned_data.get('tax'),
                    'note': item_form.cleaned_data.get('note', '')
                })

            try:
                PettyCashPaymentService.update_payment(
                    self.object,
                    updated_by=self.request.user,
                    items_data=items_data,
                    payee=form.cleaned_data.get('payee'),
                    payee_name=form.cleaned_data.get('payee_name', ''),
                    payment_date=form.cleaned_data.get('payment_date'),
                    note=form.cleaned_data.get('note', '')
                )
                messages.success(self.request, "Voucher updated successfully.")
                return redirect('accounting:payment-list', account_code=account.code)
            except ValidationError as e:
                form.add_error(None, e)
                return self.form_invalid(form)
        else:
            return self.form_invalid(form)


class PettyCashPaymentCancelView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'accounting.delete_pettycashpayment'

    def post(self, request, pk, *args, **kwargs):
        payment = get_object_or_404(PettyCashPayment, pk=pk, is_deleted=False)
        account_code = payment.account.code
        if payment.is_posted:
            messages.error(request, "This payment is posted to Express and cannot be cancelled.")
            return redirect('accounting:payment-detail', pk=payment.pk)
        try:
            PettyCashPaymentService.cancel_payment(payment, user=request.user)
            messages.success(request, "Voucher cancelled and balance reversed successfully.")
        except ValidationError as e:
            messages.error(request, e.message)
        return redirect('accounting:payment-list', account_code=account_code)


class PettyCashPaymentTrashListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = PettyCashPayment
    template_name = 'accounting/payment_trash_list.html'
    context_object_name = 'payments'
    permission_required = 'accounting.delete_pettycashpayment'

    def get_account(self):
        return get_object_or_404(PettyCashAccount, code=self.kwargs['account_code'], is_deleted=False)

    def get_queryset(self):
        account = self.get_account()
        return PettyCashPayment.objects.filter(account=account, is_deleted=True).select_related('created_by')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = self.get_account()
        return context


class PettyCashPaymentSummaryView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'accounting/payment_summary.html'
    permission_required = 'accounting.change_pettycashpayment'

    def get_account(self):
        return get_object_or_404(PettyCashAccount, code=self.kwargs['account_code'], is_deleted=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.get_account()
        context['account'] = account

        # Date Filters
        now = timezone.now()
        year = int(self.request.GET.get('year', now.year))
        month = int(self.request.GET.get('month', now.month))
        context['selected_year'] = year
        context['selected_month'] = month
        context['years'] = list(range(now.year - 4, now.year + 2))
        context['months'] = [
            (1, 'January'), (2, 'February'), (3, 'March'), (4, 'April'),
            (5, 'May'), (6, 'June'), (7, 'July'), (8, 'August'),
            (9, 'September'), (10, 'October'), (11, 'November'), (12, 'December')
        ]

        # Fetch payments in the selected month
        payments = PettyCashPayment.objects.filter(
            account=account,
            payment_date__year=year,
            payment_date__month=month,
            is_deleted=False
        )

        items = PettyCashPaymentItem.objects.filter(payment__in=payments)

        # Categorized Summary
        # SQL Group By category code/name
        category_sums = items.values('category__code', 'category__name').annotate(
            total=Sum('amount')
        ).order_by('category__code')

        # Compute unallocated items count
        unallocated_count = items.filter(category__isnull=True).count()

        context['payments'] = payments
        context['category_sums'] = category_sums
        context['unallocated_count'] = unallocated_count
        context['unposted_payments'] = payments.filter(is_posted=False)
        context['posted_payments'] = payments.filter(is_posted=True)

        return context

    def post(self, request, *args, **kwargs):
        account = self.get_account()
        year = int(request.POST.get('year', timezone.now().year))
        month = int(request.POST.get('month', timezone.now().month))

        # Fetch unposted payments to mark
        unposted_payments = PettyCashPayment.objects.filter(
            account=account,
            payment_date__year=year,
            payment_date__month=month,
            is_deleted=False,
            is_posted=False
        )

        if not unposted_payments.exists():
            messages.warning(request, "No unposted vouchers found for the selected month.")
            return redirect(f"{request.path}?year={year}&month={month}")

        try:
            PettyCashPaymentService.mark_payments_as_posted(unposted_payments, user=request.user)
            messages.success(request, f"Successfully marked {len(unposted_payments)} vouchers as posted to Express.")
        except ValidationError as e:
            messages.error(request, e.message)

        return redirect(f"{request.path}?year={year}&month={month}")
