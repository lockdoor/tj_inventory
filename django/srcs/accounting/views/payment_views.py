import datetime
from decimal import Decimal
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from accounting.models import PettyCashPayment, PettyCashAccount, PettyCashPaymentItem, PettyCashCategory
from accounting.forms.payment_form import PettyCashPaymentForm, PettyCashPaymentItemFormSet
from accounting.services.payment_service import PettyCashPaymentService
from accounting.services.excel_service import PettyCashExcelExportService


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
        
        sf_list = self.request.GET.getlist('sf')
        sv_list = self.request.GET.getlist('sv')
        
        # Also fall back to general q search if present
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(payment_no__icontains=q) |
                Q(payee_name__icontains=q) |
                Q(note__icontains=q)
            )

        for sf, sv in zip(sf_list, sv_list):
            sv = sv.strip()
            if not sv:
                continue
            if sf == 'voucher_no':
                qs = qs.filter(payment_no__icontains=sv)
            elif sf == 'payee':
                qs = qs.filter(payee_name__icontains=sv)
            elif sf == 'gl_code':
                qs = qs.filter(items__category__code__icontains=sv)
            elif sf == 'external_pv':
                qs = qs.filter(items__external_pv_no__icontains=sv)
            elif sf == 'description':
                qs = qs.filter(Q(items__description__icontains=sv) | Q(note__icontains=sv))
            else: # 'all' or fallback
                qs = qs.filter(
                    Q(payment_no__icontains=sv) |
                    Q(payee_name__icontains=sv) |
                    Q(note__icontains=sv) |
                    Q(items__category__code__icontains=sv) |
                    Q(items__external_pv_no__icontains=sv) |
                    Q(items__description__icontains=sv)
                )
                
        return qs.distinct().select_related('account', 'created_by').prefetch_related('items')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = self.get_account()
        context['q'] = self.request.GET.get('q', '')
        
        # Build search lines list for template
        sf_list = self.request.GET.getlist('sf')
        sv_list = self.request.GET.getlist('sv')
        search_lines = []
        for sf, sv in zip(sf_list, sv_list):
            if sv.strip():
                search_lines.append({'field': sf, 'value': sv.strip()})
        
        # Always guarantee at least one search line if none exist
        if not search_lines:
            search_lines.append({'field': 'all', 'value': ''})
            
        context['search_lines'] = search_lines
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
                    'note': item_form.cleaned_data.get('note', ''),
                    'external_pv_no': item_form.cleaned_data.get('external_pv_no', ''),
                    'rounding_adjustment': item_form.cleaned_data.get('rounding_adjustment')
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
        context['next'] = self.request.GET.get('next') or self.request.POST.get('next') or ''
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
                    'note': item_form.cleaned_data.get('note', ''),
                    'external_pv_no': item_form.cleaned_data.get('external_pv_no', ''),
                    'rounding_adjustment': item_form.cleaned_data.get('rounding_adjustment')
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
                next_url = self.request.GET.get('next') or self.request.POST.get('next')
                if next_url:
                    return redirect(next_url)
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

        confirm_payment_no = request.POST.get('confirm_payment_no', '').strip()
        if confirm_payment_no and confirm_payment_no != payment.payment_no:
            messages.error(request, f"Entered voucher number '{confirm_payment_no}' does not match '{payment.payment_no}'. Cancellation aborted.")
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


def get_round_data(account, round_id=None):
    """
    Given an account and optional round_id, compute:
    - replenishments: QuerySet of all replenishments ordered by (-payment_date, -id)
    - active_qs: QuerySet of payments belonging to the active (unreplenished) round
    - rounds: list of round dicts ({'id': ..., 'name': ...})
    - selected_round_id: resolved round_id
    - selected_rep: PettyCashPayment instance or None
    - prev_rep: PettyCashPayment instance or None
    - is_active_round: bool
    - payments_qs: QuerySet of PettyCashPayment belonging to this round
    """
    replenishments = PettyCashPayment.objects.filter(
        account=account,
        payment_type='replenishment',
        is_deleted=False
    ).order_by('-payment_date', '-id')

    latest_rep = replenishments.first()
    active_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)
    if latest_rep:
        active_qs = active_qs.filter(
            Q(payment_date__gt=latest_rep.payment_date) |
            Q(payment_date=latest_rep.payment_date, id__gt=latest_rep.id)
        )

    rounds = []
    if active_qs.exists():
        rounds.append({
            'id': 'active',
            'name': 'Active (Unreplenished) Round'
        })
    for rep in replenishments:
        formatted_date = rep.payment_date.strftime('%Y-%m-%d') if rep.payment_date else ''
        rounds.append({
            'id': str(rep.id),
            'name': f"Replenishment {rep.payment_no} ({formatted_date})"
        })

    if not round_id and rounds:
        round_id = rounds[0]['id']

    selected_rep = None
    prev_rep = None
    is_active_round = False

    if round_id == 'active':
        is_active_round = True
        payments_qs = active_qs
    elif round_id:
        try:
            selected_rep = replenishments.get(pk=int(round_id))
            prev_rep = replenishments.filter(
                Q(payment_date__lt=selected_rep.payment_date) |
                Q(payment_date=selected_rep.payment_date, id__lt=selected_rep.id)
            ).order_by('-payment_date', '-id').first()

            payments_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)
            if prev_rep:
                payments_qs = payments_qs.filter(
                    (Q(payment_date__gt=prev_rep.payment_date) | Q(payment_date=prev_rep.payment_date, id__gt=prev_rep.id)) &
                    (Q(payment_date__lt=selected_rep.payment_date) | Q(payment_date=selected_rep.payment_date, id__lte=selected_rep.id))
                )
            else:
                payments_qs = payments_qs.filter(
                    Q(payment_date__lt=selected_rep.payment_date) |
                    Q(payment_date=selected_rep.payment_date, id__lte=selected_rep.id)
                )
        except (ValueError, PettyCashPayment.DoesNotExist):
            payments_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)
    else:
        payments_qs = PettyCashPayment.objects.none()

    return {
        'replenishments': replenishments,
        'active_qs': active_qs,
        'rounds': rounds,
        'selected_round_id': round_id,
        'selected_rep': selected_rep,
        'prev_rep': prev_rep,
        'is_active_round': is_active_round,
        'payments_qs': payments_qs,
    }


def filter_payments_by_search(payments_qs, query_params):
    """
    Applies multi-condition search filtering to payments_qs based on query_params:
    - q: general text search across payment_no, payee_name, note
    - sf / sv: field-specific search (voucher_no, payee, gl_code, external_pv, description, all)
    """
    sf_list = query_params.getlist('sf')
    sv_list = query_params.getlist('sv')

    q = query_params.get('q', '').strip()
    if q:
        payments_qs = payments_qs.filter(
            Q(payment_no__icontains=q) |
            Q(payee_name__icontains=q) |
            Q(note__icontains=q)
        )

    for sf, sv in zip(sf_list, sv_list):
        sv = sv.strip()
        if not sv:
            continue
        if sf == 'voucher_no':
            payments_qs = payments_qs.filter(payment_no__icontains=sv)
        elif sf == 'payee':
            payments_qs = payments_qs.filter(payee_name__icontains=sv)
        elif sf == 'gl_code':
            payments_qs = payments_qs.filter(items__category__code__icontains=sv)
        elif sf == 'external_pv':
            payments_qs = payments_qs.filter(items__external_pv_no__icontains=sv)
        elif sf == 'description':
            payments_qs = payments_qs.filter(Q(items__description__icontains=sv) | Q(note__icontains=sv))
        else:
            payments_qs = payments_qs.filter(
                Q(payment_no__icontains=sv) |
                Q(payee_name__icontains=sv) |
                Q(note__icontains=sv) |
                Q(items__category__code__icontains=sv) |
                Q(items__external_pv_no__icontains=sv) |
                Q(items__description__icontains=sv)
            )

    return payments_qs.distinct()


def calculate_category_sums(account, payments_qs):
    """
    Computes category aggregations including net normal expense categories,
    VAT extraction lines, rounding adjustment lines, pending allocation lines,
    and external PV items.
    Returns: (category_sums_list, unallocated_count)
    """
    items = PettyCashPaymentItem.objects.filter(payment__in=payments_qs)
    round_items = items.exclude(payment__payment_type='replenishment')

    # Distinguish actual PV items and normal items
    actual_pv_items = round_items.exclude(external_pv_no='').exclude(external_pv_no__isnull=True).order_by('external_pv_no', 'id')
    normal_items = round_items.filter(Q(external_pv_no='') | Q(external_pv_no__isnull=True))

    # In-memory aggregation of normal items with VAT extraction and rounding adjustment deduction
    category_sums_dict = {}
    unallocated_sum = Decimal('0.00')

    # Prefetch payment to avoid N+1 queries on item.payment
    normal_items = normal_items.select_related('payment')

    vat_items_list = []
    rounding_items_list = []
    for item in normal_items:
        tax_amount = item.tax or Decimal('0.00')
        item_rounding = item.rounding_adjustment or Decimal('0.00')

        net_amount = item.amount - tax_amount - item_rounding

        if tax_amount > Decimal('0.00'):
            vat_code = account.vat_category_code or '1155-00'
            vat_cat = PettyCashCategory.objects.filter(code=vat_code, company=account.company, is_deleted=False).first()
            vat_name = vat_cat.name if vat_cat else "ภาษีซื้อ-ยังไม่ถึงกำหนด"
            payee = item.payment.payee_name or (item.payment.created_by.get_full_name() if item.payment.created_by else '') or str(item.payment.created_by or '')
            desc_str = f"VAT: {payee} - {item.description}" if payee and item.description else (payee or item.description or 'Input VAT')
            vat_items_list.append({
                'category__code': vat_code,
                'category__name': f"{vat_name} ({desc_str})",
                'category_base_name': vat_name,
                'total': tax_amount
            })

        if item_rounding != Decimal('0.00'):
            rounding_code = account.rounding_category_code or '4200-07'
            rounding_cat = PettyCashCategory.objects.filter(code=rounding_code, company=account.company, is_deleted=False).first()
            rounding_name = rounding_cat.name if rounding_cat else "รายได้-อื่นๆ"
            payee = item.payment.payee_name or (item.payment.created_by.get_full_name() if item.payment.created_by else '') or str(item.payment.created_by or '')
            desc_str = f"Rounding: {payee} - {item.description}" if payee and item.description else (payee or item.description or 'Rounding Adjustment')
            rounding_items_list.append({
                'category__code': rounding_code,
                'category__name': f"{rounding_name} ({desc_str})",
                'category_base_name': rounding_name,
                'total': item_rounding
            })

        if item.category:
            code = item.category.code
            name = item.category.name
            if code not in category_sums_dict:
                category_sums_dict[code] = {
                    'category__code': code,
                    'category__name': name,
                    'category_base_name': name,
                    'total': Decimal('0.00')
                }
            category_sums_dict[code]['total'] += net_amount
        else:
            unallocated_sum += net_amount

    # Convert to list and sort normal categories by code
    category_sums_list = sorted(category_sums_dict.values(), key=lambda x: x['category__code'])

    # Append individual VAT records
    category_sums_list.extend(vat_items_list)

    # Append individual rounding records
    category_sums_list.extend(rounding_items_list)

    # Append unallocated row if it exists
    if unallocated_sum > Decimal('0.00'):
        category_sums_list.append({
            'category__code': None,
            'category__name': "Pending category allocation",
            'category_base_name': "Pending category allocation",
            'total': unallocated_sum
        })

    # Append individual actual PV records
    for item in actual_pv_items:
        payment = item.payment
        payee = payment.payee_name or (payment.payee.full_name if payment.payee else '') or str(payment.payee or '')
        desc_str = f"{payee} - {item.description}" if payee and item.description else (payee or item.description or 'External PV')
        category_sums_list.append({
            'category__code': f"PV: {item.external_pv_no}",
            'category__name': desc_str,
            'category_base_name': desc_str,
            'total': item.amount
        })

    # Compute unallocated count, excluding items belonging to replenishment or actual PV items
    unallocated_count = items.filter(category__isnull=True).exclude(payment__payment_type='replenishment').exclude(
        ~Q(external_pv_no='') & Q(external_pv_no__isnull=False)
    ).count()

    return category_sums_list, unallocated_count


class PettyCashPaymentSummaryView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    template_name = 'accounting/payment_summary.html'
    permission_required = 'accounting.change_pettycashpayment'

    def get_account(self):
        return get_object_or_404(PettyCashAccount, code=self.kwargs['account_code'], is_deleted=False)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        account = self.get_account()
        context['account'] = account

        round_id = self.request.GET.get('round_id')
        round_data = get_round_data(account, round_id)

        rounds = round_data['rounds']
        round_id = round_data['selected_round_id']
        context['rounds'] = rounds
        context['selected_round_id'] = round_id

        # Calculate prev/next round navigation
        prev_round = None
        next_round = None
        current_idx = None
        for i, rnd in enumerate(rounds):
            if rnd['id'] == round_id:
                current_idx = i
                break
        
        if current_idx is not None:
            if current_idx < len(rounds) - 1:
                prev_round = rounds[current_idx + 1]  # Older
            if current_idx > 0:
                next_round = rounds[current_idx - 1]  # Newer
        
        context['prev_round'] = prev_round
        context['next_round'] = next_round

        selected_rep = round_data['selected_rep']
        is_active_round = round_data['is_active_round']
        payments_qs = filter_payments_by_search(round_data['payments_qs'], self.request.GET)

        # Build search lines list for template
        sf_list = self.request.GET.getlist('sf')
        sv_list = self.request.GET.getlist('sv')
        q = self.request.GET.get('q', '').strip()

        category_sums_list, unallocated_count = calculate_category_sums(account, payments_qs)

        context['payments'] = payments_qs
        context['category_sums'] = category_sums_list
        context['total_spent'] = sum(row['total'] for row in category_sums_list)
        context['unallocated_count'] = unallocated_count
        context['unposted_payments'] = payments_qs.filter(is_posted=False)
        context['posted_payments'] = payments_qs.filter(is_posted=True)
        context['is_active_round'] = is_active_round
        context['selected_rep'] = selected_rep

        return context

    def post(self, request, *args, **kwargs):
        account = self.get_account()
        round_id = request.POST.get('round_id')

        if round_id == 'active':
            messages.error(request, "You cannot lock the active round until a replenishment record is created.")
            return redirect(f"{request.path}?round_id=active")

        round_data = get_round_data(account, round_id)
        selected_rep = round_data['selected_rep']
        if not selected_rep:
            selected_rep = get_object_or_404(PettyCashPayment, pk=int(round_id), account=account)

        payments_qs = round_data['payments_qs']
        action = request.POST.get('action', 'lock')

        confirm_payment_no = request.POST.get('confirm_payment_no', '').strip()
        expected_pv = selected_rep.payment_no if selected_rep else ''
        if confirm_payment_no and expected_pv:
            valid_confirmations = [expected_pv]
            if action == 'lock':
                valid_confirmations.append('LOCK')
            elif action == 'unlock':
                valid_confirmations.append('UNLOCK')
            if confirm_payment_no not in valid_confirmations:
                messages.error(request, f"Entered confirmation '{confirm_payment_no}' does not match '{expected_pv}'. Action aborted.")
                return redirect(f"{request.path}?round_id={round_id}")

        if action == 'unlock':
            posted_payments = payments_qs.filter(is_posted=True)
            if not posted_payments.exists():
                messages.warning(request, "No posted vouchers found to unlock for the selected round.")
                return redirect(f"{request.path}?round_id={round_id}")

            try:
                PettyCashPaymentService.mark_payments_as_unposted(posted_payments, user=request.user)
                messages.success(request, f"Successfully unlocked {len(posted_payments)} vouchers for this round.")
            except ValidationError as e:
                messages.error(request, e.message)

            return redirect(f"{request.path}?round_id={round_id}")

        unposted_payments = payments_qs.filter(is_posted=False)

        if not unposted_payments.exists():
            messages.warning(request, "No unposted vouchers found for the selected round.")
            return redirect(f"{request.path}?round_id={round_id}")

        try:
            PettyCashPaymentService.mark_payments_as_posted(unposted_payments, user=request.user)
            messages.success(request, f"Successfully marked {len(unposted_payments)} vouchers as posted to Express.")
        except ValidationError as e:
            messages.error(request, e.message)

        return redirect(f"{request.path}?round_id={round_id}")


class PettyCashCategorySearchAPIView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()
        company_id = request.GET.get('company_id')
        payment_id = request.GET.get('payment_id')
        
        qs = PettyCashCategory.objects.filter(is_deleted=False)
        if payment_id:
            payment = get_object_or_404(PettyCashPayment, pk=payment_id)
            qs = qs.filter(company=payment.account.company)
        elif company_id:
            qs = qs.filter(company_id=company_id)
            
        if q:
            qs = qs.filter(Q(code__icontains=q) | Q(name__icontains=q))
            
        # Limit to top 15 results for performance
        results = [
            {'id': cat.id, 'code': cat.code, 'name': cat.name}
            for cat in qs[:15]
        ]
        return JsonResponse({'results': results})


class PettyCashPaymentAllocateAPIView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'accounting.change_pettycashpayment'
    
    def post(self, request, pk, *args, **kwargs):
        item = get_object_or_404(PettyCashPaymentItem, pk=pk)
        if item.payment.is_posted:
            return JsonResponse({'error': 'Cannot modify posted vouchers.'}, status=400)
            
        import json
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON.'}, status=400)
            
        category_id = data.get('category_id')
        external_pv_no = data.get('external_pv_no')
        
        if not category_id and not external_pv_no:
            return JsonResponse({'error': 'Either Category or External PV number is required.'}, status=400)
            
        if category_id:
            category = get_object_or_404(PettyCashCategory, pk=category_id, is_deleted=False)
            if category.company != item.payment.account.company:
                return JsonResponse({'error': 'Category company mismatch.'}, status=400)
                
            item.category = category
            item.external_pv_no = ''
            item.save()
        else:
            item.category = None
            item.external_pv_no = external_pv_no.strip()
            item.save()
            
        return JsonResponse({'success': True})


class PettyCashPaymentSummaryExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'accounting.view_pettycashpayment'

    def get_account(self, account_code):
        return get_object_or_404(PettyCashAccount, code=account_code, is_deleted=False)

    def get(self, request, account_code, *args, **kwargs):
        account = self.get_account(account_code)
        round_id = request.GET.get('round_id')
        round_data = get_round_data(account, round_id)

        selected_rep = round_data['selected_rep']
        payments_qs = filter_payments_by_search(round_data['payments_qs'], request.GET)

        items = PettyCashPaymentItem.objects.filter(
            payment__in=payments_qs
        ).exclude(
            payment__payment_type='replenishment'
        ).select_related('payment', 'payment__payee').order_by('payment__payment_date', 'payment__id', 'id')

        buffer, filename = PettyCashExcelExportService.generate_replenishment_vouchers_excel(
            account, round_id, selected_rep, items
        )

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class PettyCashCategorySummaryExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'accounting.view_pettycashpayment'

    def get_account(self, account_code):
        return get_object_or_404(PettyCashAccount, code=account_code, is_deleted=False)

    def get(self, request, account_code, *args, **kwargs):
        account = self.get_account(account_code)
        round_id = request.GET.get('round_id')
        round_data = get_round_data(account, round_id)

        selected_rep = round_data['selected_rep']
        payments_qs = filter_payments_by_search(round_data['payments_qs'], request.GET)

        category_sums_list, _ = calculate_category_sums(account, payments_qs)

        buffer, filename = PettyCashExcelExportService.generate_category_summary_excel(
            account, round_id, selected_rep, category_sums_list
        )

        response = HttpResponse(
            buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

