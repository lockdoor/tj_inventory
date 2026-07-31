import datetime
from decimal import Decimal
from django.views.generic import ListView, DetailView, CreateView, UpdateView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.utils import timezone
from accounting.models import PettyCashPayment, PettyCashAccount, PettyCashPaymentItem, PettyCashCategory
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
                    note=form.cleaned_data.get('note', ''),
                    rounding_adjustment=form.cleaned_data.get('rounding_adjustment')
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
                    note=form.cleaned_data.get('note', ''),
                    rounding_adjustment=form.cleaned_data.get('rounding_adjustment')
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

        # Fetch replenishments to build rounds
        replenishments = PettyCashPayment.objects.filter(
            account=account,
            payment_type='replenishment',
            is_deleted=False
        ).order_by('-payment_date', '-id')

        # Check Active (Unreplenished) Round
        latest_rep = replenishments.first()
        active_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)
        if latest_rep:
            active_qs = active_qs.filter(id__gt=latest_rep.id)

        # Build dropdown options
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
        context['rounds'] = rounds

        # Determine selected round
        round_id = self.request.GET.get('round_id')
        if not round_id and rounds:
            round_id = rounds[0]['id']
        context['selected_round_id'] = round_id

        selected_rep = None
        is_active_round = False

        if round_id == 'active':
            is_active_round = True
            payments_qs = active_qs
        elif round_id:
            try:
                selected_rep = replenishments.get(pk=int(round_id))
                prev_rep = replenishments.filter(id__lt=selected_rep.id).order_by('-id').first()
                payments_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)
                if prev_rep:
                    payments_qs = payments_qs.filter(id__gt=prev_rep.id, id__lte=selected_rep.id)
                else:
                    payments_qs = payments_qs.filter(id__lte=selected_rep.id)
            except (ValueError, PettyCashPayment.DoesNotExist):
                payments_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)
        else:
            payments_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)

        items = PettyCashPaymentItem.objects.filter(payment__in=payments_qs)
        
        round_items = items.exclude(payment__payment_type='replenishment')

        # Distinguish actual PV payments and normal items
        actual_pv_payments = payments_qs.exclude(payment_type='replenishment').exclude(external_pv_no='').exclude(external_pv_no__isnull=True).order_by('external_pv_no', 'id')
        normal_items = round_items.exclude(payment__in=actual_pv_payments)

        # In-memory aggregation of normal items with VAT extraction and rounding adjustment deduction
        category_sums_dict = {}
        total_vat = Decimal('0.00')
        total_rounding = Decimal('0.00')
        unallocated_sum = Decimal('0.00')
        processed_payment_ids = set()

        # Prefetch payment to avoid N+1 queries on item.payment.rounding_adjustment
        normal_items = normal_items.select_related('payment')

        for item in normal_items:
            tax_amount = item.tax or Decimal('0.00')
            item_rounding = Decimal('0.00')
            
            # If this is the first item of the payment, subtract the rounding adjustment
            if item.payment_id not in processed_payment_ids:
                if item.payment.rounding_adjustment:
                    item_rounding = item.payment.rounding_adjustment
                    total_rounding += item_rounding
                processed_payment_ids.add(item.payment_id)

            net_amount = item.amount - tax_amount - item_rounding
            total_vat += tax_amount

            if item.category:
                code = item.category.code
                name = item.category.name
                if code not in category_sums_dict:
                    category_sums_dict[code] = {
                        'category__code': code,
                        'category__name': name,
                        'total': Decimal('0.00')
                    }
                category_sums_dict[code]['total'] += net_amount
            else:
                unallocated_sum += net_amount

        # Add VAT aggregation under the configured VAT code if VAT exists
        if total_vat > Decimal('0.00'):
            vat_code = account.vat_category_code or '1155-00'
            if vat_code in category_sums_dict:
                category_sums_dict[vat_code]['total'] += total_vat
            else:
                vat_cat = PettyCashCategory.objects.filter(code=vat_code, company=account.company, is_deleted=False).first()
                vat_name = vat_cat.name if vat_cat else "ภาษีซื้อ-ยังไม่ถึงกำหนด"
                category_sums_dict[vat_code] = {
                    'category__code': vat_code,
                    'category__name': vat_name,
                    'total': total_vat
                }

        # Add Rounding aggregation under the configured rounding category code if rounding exists
        if total_rounding != Decimal('0.00'):
            rounding_code = account.rounding_category_code or '4200-07'
            if rounding_code in category_sums_dict:
                category_sums_dict[rounding_code]['total'] += total_rounding
            else:
                rounding_cat = PettyCashCategory.objects.filter(code=rounding_code, company=account.company, is_deleted=False).first()
                rounding_name = rounding_cat.name if rounding_cat else "รายได้-อื่นๆ"
                category_sums_dict[rounding_code] = {
                    'category__code': rounding_code,
                    'category__name': rounding_name,
                    'total': total_rounding
                }

        # Convert to list and sort normal categories by code
        category_sums_list = sorted(category_sums_dict.values(), key=lambda x: x['category__code'])

        # Append unallocated row if it exists
        if unallocated_sum > Decimal('0.00'):
            category_sums_list.append({
                'category__code': None,
                'category__name': "Pending category allocation",
                'total': unallocated_sum
            })

        # Append individual actual PV records
        for payment in actual_pv_payments:
            payee = payment.payee_name or (payment.payee.get_full_name() if payment.payee else '') or str(payment.payee or '')
            first_item_desc = payment.items.first().description if payment.items.exists() else ''
            desc_str = f"{payee} - {first_item_desc}" if payee and first_item_desc else (payee or first_item_desc or 'External PV')
            category_sums_list.append({
                'category__code': f"PV: {payment.external_pv_no}",
                'category__name': desc_str,
                'total': payment.total_amount
            })

        # Compute unallocated count, excluding items belonging to replenishment or actual PV payments
        unallocated_count = items.filter(category__isnull=True).exclude(payment__payment_type='replenishment').exclude(
            Q(payment__external_pv_no__isnull=False) & ~Q(payment__external_pv_no='')
        ).count()

        context['payments'] = payments_qs
        context['category_sums'] = category_sums_list
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

        selected_rep = get_object_or_404(PettyCashPayment, pk=int(round_id), account=account)
        replenishments = PettyCashPayment.objects.filter(
            account=account,
            payment_type='replenishment',
            is_deleted=False
        ).order_by('-id')
        prev_rep = replenishments.filter(id__lt=selected_rep.id).first()

        payments_qs = PettyCashPayment.objects.filter(account=account, is_deleted=False)
        if prev_rep:
            payments_qs = payments_qs.filter(id__gt=prev_rep.id, id__lte=selected_rep.id)
        else:
            payments_qs = payments_qs.filter(id__lte=selected_rep.id)

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
        payment = get_object_or_404(PettyCashPayment, pk=pk)
        if payment.is_posted:
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
            if category.company != payment.account.company:
                return JsonResponse({'error': 'Category company mismatch.'}, status=400)
                
            payment.external_pv_no = ''
            payment.save()
            
            item = payment.items.first()
            if not item:
                item = PettyCashPaymentItem.objects.create(
                    payment=payment,
                    amount=payment.total_amount,
                    category=category,
                    description=payment.note or "Voucher Item"
                )
            else:
                item.category = category
                item.save()
        else:
            # Clear categories on items and set external PV
            payment.external_pv_no = external_pv_no.strip()
            payment.save()
            
            for item in payment.items.all():
                item.category = None
                item.save()
            
        return JsonResponse({'success': True})
