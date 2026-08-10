import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from django.utils import timezone
from common.models import Company, Individual
from accounting.models import PettyCashAccount, PettyCashCategory, PettyCashPayment, PettyCashPaymentItem
from accounting.services.payment_service import PettyCashPaymentService

@pytest.fixture
def manager_user(db):
    user = User.objects.create_user("manager", "manager@test.com", "pass")
    content_type_pay = ContentType.objects.get_for_model(PettyCashPayment)
    perms = Permission.objects.filter(content_type=content_type_pay)
    user.user_permissions.add(*perms)
    
    # Also need view permission for account
    content_type_acc = ContentType.objects.get_for_model(PettyCashAccount)
    acc_perms = Permission.objects.filter(content_type=content_type_acc)
    user.user_permissions.add(*acc_perms)
    return user

@pytest.fixture
def company(db, manager_user):
    return Company.objects.create(
        code="TJ",
        name="TJ Company",
        created_by=manager_user
    )

@pytest.fixture
def custodian_user(db):
    return User.objects.create_user("custodian", "custodian@test.com", "pass")

@pytest.fixture
def account(db, company, custodian_user, manager_user):
    return PettyCashAccount.objects.create(
        code="PC-HO-01",
        name="Head Office Box",
        company=company,
        custodian=custodian_user,
        balance=Decimal("5000.00"),
        max_limit=Decimal("10000.00"),
        created_by=manager_user
    )

@pytest.fixture
def category(db, company, manager_user):
    return PettyCashCategory.objects.create(
        code="5101-01",
        name="Travel Expenses",
        company=company,
        created_by=manager_user
    )

@pytest.fixture
def payee_individual(db, manager_user):
    return Individual.objects.create(
        first_name_th="สมชาย",
        last_name_th="ดีใจ",
        created_by=manager_user
    )

@pytest.fixture
def payment(db, account, category, payee_individual, manager_user):
    # Create standard disbursement of 1000.00
    payment = PettyCashPayment.objects.create(
        account=account,
        payment_type="disbursement",
        total_amount=Decimal("1000.00"),
        payee=payee_individual,
        payee_name="Custodian User",
        created_by=manager_user
    )
    PettyCashPaymentItem.objects.create(
        payment=payment,
        category=category,
        amount=Decimal("1000.00"),
        description="Taxi fare"
    )
    # Deduct from account balance
    account.balance -= Decimal("1000.00")
    account.save()
    return payment

@pytest.mark.django_db
class TestPettyCashPaymentViews:

    def test_list_view(self, client, manager_user, account, payment):
        client.force_login(manager_user)
        url = reverse('accounting:payment-list', kwargs={'account_code': account.code})
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context['payments']) == 1
        assert response.context['account'] == account

        # Test search matching payment_no
        response = client.get(url, {'q': payment.payment_no})
        assert response.status_code == 200
        assert len(response.context['payments']) == 1

        # Test search matching payee_name
        payment.payee_name = "Unique Payee Name"
        payment.save()
        response = client.get(url, {'q': 'Unique Payee'})
        assert response.status_code == 200
        assert len(response.context['payments']) == 1

        # Test search non-matching query
        response = client.get(url, {'q': 'NonExistentSearchTerm'})
        assert response.status_code == 200
        assert len(response.context['payments']) == 0

        # Test advanced search matching gl_code
        response = client.get(url, {'sf': ['gl_code'], 'sv': ['5101-01']})
        assert response.status_code == 200
        assert len(response.context['payments']) == 1

        # Test advanced search matching multiple conditions (gl_code AND payee)
        response = client.get(url, {'sf': ['gl_code', 'payee'], 'sv': ['5101-01', 'Unique Payee']})
        assert response.status_code == 200
        assert len(response.context['payments']) == 1

        # Test advanced search mismatching second condition
        response = client.get(url, {'sf': ['gl_code', 'payee'], 'sv': ['5101-01', 'Incorrect Payee']})
        assert response.status_code == 200
        assert len(response.context['payments']) == 0

    def test_create_payment_success(self, client, manager_user, account, category):
        client.force_login(manager_user)
        
        # Verify initial balance is 5000.00
        assert account.balance == Decimal("5000.00")
        
        url = reverse('accounting:payment-create', kwargs={'account_code': account.code})
        data = {
            'payment_type': 'disbursement',
            'payment_date': '2026-07-03',
            'payee_name': 'Somchai',
            'note': 'Office groceries',
            
            # Formset management form
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            
            # Formset line item
            'items-0-category': category.pk,
            'items-0-description': 'Coffee & milk',
            'items-0-amount': '300.00',
            'items-0-note': 'Receipt 123'
        }
        
        response = client.post(url, data)
        assert response.status_code == 302
        
        # Verify payment created & balance deducted (5000.00 - 300.00 = 4700.00)
        account.refresh_from_db()
        assert account.balance == Decimal("4700.00")
        assert PettyCashPayment.objects.filter(payee_name='Somchai').exists()

    def test_create_payment_with_unallocated_category(self, client, manager_user, account):
        """Accountant 1 should be allowed to create a disbursement with no category assigned."""
        client.force_login(manager_user)
        url = reverse('accounting:payment-create', kwargs={'account_code': account.code})
        data = {
            'payment_type': 'disbursement',
            'payment_date': '2026-07-03',
            'payee_name': 'Somchai Unallocated',
            
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            
            # Formset line item (category left blank/None)
            'items-0-category': '',
            'items-0-description': 'Taxi fare pending review',
            'items-0-amount': '250.00',
            'items-0-note': ''
        }
        response = client.post(url, data)
        assert response.status_code == 302
        
        # Balance deducted
        account.refresh_from_db()
        assert account.balance == Decimal("4750.00")
        
        # Verify category is null on database record
        p = PettyCashPayment.objects.get(payee_name='Somchai Unallocated')
        assert p.items.first().category is None

    def test_create_payment_insufficient_funds(self, client, manager_user, account, category):
        client.force_login(manager_user)
        url = reverse('accounting:payment-create', kwargs={'account_code': account.code})
        data = {
            'payment_type': 'disbursement',
            'payment_date': '2026-07-03',
            
            # Formset management form
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '0',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            
            # Line item exceeding balance of 5000.00
            'items-0-category': category.pk,
            'items-0-description': 'Expensive equipment',
            'items-0-amount': '6000.00',
            'items-0-note': ''
        }
        
        response = client.post(url, data)
        assert response.status_code == 200  # Renders form again with error
        
        # Balance remains unchanged
        account.refresh_from_db()
        assert account.balance == Decimal("5000.00")

    def test_update_payment_recalculates_balance(self, client, manager_user, account, category, payment):
        client.force_login(manager_user)
        
        # Current balance is 4000.00 (disbursement of 1000.00 was already applied)
        assert account.balance == Decimal("4000.00")
        
        url = reverse('accounting:payment-update', kwargs={'pk': payment.pk})
        
        # We increase the line amount to 1500.00 (+500.00 difference)
        data = {
            'payment_type': 'disbursement',
            'payment_date': '2026-07-03',
            'payee_name': 'Custodian User Updated',
            
            # Formset management form
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '1',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            
            # Existing Line item updated
            'items-0-id': payment.items.first().pk,
            'items-0-category': category.pk,
            'items-0-description': 'Taxi fare longer route',
            'items-0-amount': '1500.00',
            'items-0-note': ''
        }
        
        response = client.post(url, data)
        assert response.status_code == 302
        
        # Re-fetch and check: balance decreased by difference of 500.00 (4000.00 - 500.00 = 3500.00)
        account.refresh_from_db()
        assert account.balance == Decimal("3500.00")
        
        payment.refresh_from_db()
        assert payment.total_amount == Decimal("1500.00")

    def test_update_payment_redirects_to_next(self, client, manager_user, account, category, payment):
        client.force_login(manager_user)
        
        url = reverse('accounting:payment-update', kwargs={'pk': payment.pk})
        target_next = '/accounting/payments/account/PC-HO-01/summary/'
        
        data = {
            'payment_type': 'disbursement',
            'payment_date': '2026-07-03',
            'payee_name': 'Custodian User Updated',
            
            # Formset management form
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '1',
            'items-MIN_NUM_FORMS': '0',
            'items-MAX_NUM_FORMS': '1000',
            
            # Existing Line item updated
            'items-0-id': payment.items.first().pk,
            'items-0-category': category.pk,
            'items-0-description': 'Taxi fare longer route',
            'items-0-amount': '1000.00',
            'items-0-note': ''
        }
        
        response = client.post(url + f"?next={target_next}", data)
        assert response.status_code == 302
        assert response.url == target_next

    def test_cancel_payment_reverses_balance(self, client, manager_user, account, payment):
        client.force_login(manager_user)
        
        # Current balance is 4000.00 (disbursement of 1000.00 was applied)
        assert account.balance == Decimal("4000.00")
        
        url = reverse('accounting:payment-cancel', kwargs={'pk': payment.pk})
        response = client.post(url)
        assert response.status_code == 302
        
        # Payment is soft-deleted
        payment.refresh_from_db()
        assert payment.is_deleted is True
        
        # Account balance is restored back to 5000.00
        account.refresh_from_db()
        assert account.balance == Decimal("5000.00")

    def test_posted_payment_locking_controls(self, client, manager_user, payment, category):
        """Posted payments cannot be updated or cancelled."""
        client.force_login(manager_user)
        
        # Mark payment as posted
        payment.is_posted = True
        payment.save()
        
        # 1. Try to update
        update_url = reverse('accounting:payment-update', kwargs={'pk': payment.pk})
        data = {
            'payment_type': 'disbursement',
            'payment_date': '2026-07-03',
            'items-TOTAL_FORMS': '1',
            'items-INITIAL_FORMS': '1',
            'items-0-id': payment.items.first().pk,
            'items-0-category': category.pk,
            'items-0-amount': '1200.00',
        }
        response = client.post(update_url, data)
        assert response.status_code == 302  # Redirects with error message
        
        # Verify amount remains unchanged
        payment.refresh_from_db()
        assert payment.total_amount == Decimal("1000.00")
        
        # 2. Try to cancel
        cancel_url = reverse('accounting:payment-cancel', kwargs={'pk': payment.pk})
        response = client.post(cancel_url)
        assert response.status_code == 302
        
        # Verify not soft-deleted
        payment.refresh_from_db()
        assert payment.is_deleted is False

    def test_summary_view_and_eom_posting(self, client, manager_user, account, payment):
        """Accountant 2 reviews aggregated categories and posts them to Express."""
        client.force_login(manager_user)
        
        # Create a replenishment to mark the end of the round
        replenishment = PettyCashPayment.objects.create(
            account=account,
            payment_type="replenishment",
            total_amount=Decimal("500.00"),
            created_by=manager_user
        )
        
        # Check GET summary page
        url = reverse('accounting:payment-summary', kwargs={'account_code': account.code})
        response = client.get(url, {'round_id': str(replenishment.id)})
        assert response.status_code == 200
        assert len(response.context['category_sums']) == 1
        assert response.context['unallocated_count'] == 0
        
        # Post the round's vouchers
        post_data = {
            'round_id': str(replenishment.id)
        }
        response = client.post(url, post_data)
        assert response.status_code == 302
        
        # Verify payment is posted in DB
        payment.refresh_from_db()
        assert payment.is_posted is True
        assert payment.posted_by == manager_user
        assert payment.posted_at is not None

    def test_summary_view_posting_fails_if_unallocated(self, client, manager_user, account):
        """Should fail posting to Express if there are unallocated items in the summary period."""
        client.force_login(manager_user)
        
        # Create a payment with no category
        unallocated_payment = PettyCashPayment.objects.create(
            account=account,
            payment_type="disbursement",
            total_amount=Decimal("150.00"),
            created_by=manager_user
        )
        PettyCashPaymentItem.objects.create(
            payment=unallocated_payment,
            category=None,  # Unallocated
            amount=Decimal("150.00")
        )
        
        # Create a replenishment to mark the end of the round
        replenishment = PettyCashPayment.objects.create(
            account=account,
            payment_type="replenishment",
            total_amount=Decimal("150.00"),
            created_by=manager_user
        )
        
        url = reverse('accounting:payment-summary', kwargs={'account_code': account.code})
        post_data = {
            'round_id': str(replenishment.id)
        }
        response = client.post(url, post_data)
        assert response.status_code == 302
        
        # Verify payment status is still unposted due to validation failure
        unallocated_payment.refresh_from_db()
        assert unallocated_payment.is_posted is False

    def test_category_search_api(self, client, manager_user, company, category):
        client.force_login(manager_user)
        url = reverse('accounting:category-search')
        
        # Test search with company_id and query
        response = client.get(url, {'company_id': company.id, 'q': category.code[:3]})
        assert response.status_code == 200
        data = response.json()
        assert len(data['results']) >= 1
        assert data['results'][0]['code'] == category.code

    def test_payment_allocate_api(self, client, manager_user, payment, category):
        client.force_login(manager_user)
        url = reverse('accounting:payment-allocate', kwargs={'pk': payment.pk})
        
        # Remove current category from items to make it unallocated
        item = payment.items.first()
        item.category = None
        item.save()
        
        # Allocate category via API
        import json
        response = client.post(
            url, 
            data=json.dumps({'category_id': category.id}), 
            content_type='application/json'
        )
        assert response.status_code == 200
        assert response.json()['success'] is True
        
        item.refresh_from_db()
        assert item.category == category

    def test_summary_view_with_vat_and_external_pv(self, client, manager_user, account, company):
        client.force_login(manager_user)
        
        # 1. Create categories: 5101-00 and 1155-00 (VAT category)
        cat_normal = PettyCashCategory.objects.create(
            company=company,
            code="5101-00",
            name="Normal Expense",
            created_by=manager_user
        )
        cat_vat = PettyCashCategory.objects.create(
            company=company,
            code="1155-00",
            name="ภาษีซื้อ-ยังไม่ถึงกำหนด",
            created_by=manager_user
        )
        
        # 2. Payment A: Normal with tax (Amount 1000.00, Tax 70.00)
        pay_a = PettyCashPayment.objects.create(
            account=account,
            payment_type="disbursement",
            total_amount=Decimal("1000.00"),
            payee_name="Somchai",
            created_by=manager_user
        )
        PettyCashPaymentItem.objects.create(
            payment=pay_a,
            category=cat_normal,
            amount=Decimal("1000.00"),
            tax=Decimal("70.00"),
            description="Taxi fare with tax receipt"
        )
        
        # 3. Payment B: Normal without tax (Amount 500.00, Tax 0.00)
        pay_b = PettyCashPayment.objects.create(
            account=account,
            payment_type="disbursement",
            total_amount=Decimal("500.00"),
            created_by=manager_user
        )
        PettyCashPaymentItem.objects.create(
            payment=pay_b,
            category=cat_normal,
            amount=Decimal("500.00"),
            tax=Decimal("0.00"),
            description="Courier service"
        )
        
        # 4. Payment C: Allocation already on 1155-00 directly (Amount 200.00, Tax 0.00)
        pay_c = PettyCashPayment.objects.create(
            account=account,
            payment_type="disbursement",
            total_amount=Decimal("200.00"),
            created_by=manager_user
        )
        PettyCashPaymentItem.objects.create(
            payment=pay_c,
            category=cat_vat,
            amount=Decimal("200.00"),
            tax=Decimal("0.00"),
            description="Direct VAT allocation"
        )
        
        # 5. Payment D: External PV (Amount 300.00, external_pv_no="PV-6902-001")
        pay_d = PettyCashPayment.objects.create(
            account=account,
            payment_type="disbursement",
            total_amount=Decimal("300.00"),
            created_by=manager_user
        )
        PettyCashPaymentItem.objects.create(
            payment=pay_d,
            category=None,
            amount=Decimal("300.00"),
            description="Direct Express PV Entry",
            external_pv_no="PV-6902-001"
        )
        
        # Create a replenishment to mark the end of the round
        replenishment = PettyCashPayment.objects.create(
            account=account,
            payment_type="replenishment",
            total_amount=Decimal("2000.00"),
            created_by=manager_user
        )
        
        # GET request to summary view for this round
        url = reverse('accounting:payment-summary', kwargs={'account_code': account.code})
        response = client.get(url, {'round_id': str(replenishment.id)})
        assert response.status_code == 200
        
        category_sums = response.context['category_sums']
        # We expect:
        # - Code "5101-00" with net amount: (1000 - 70) + 500 = 1430.00
        # - Code "1155-00" with base + tax: 200 + 70 = 270.00
        # - Code "PV: PV-6902-001" with amount: 300.00
        
        # VAT is now individual rows instead of a single aggregated row.
        vat_rows = [row for row in category_sums if row['category__code'] == "1155-00"]
        total_vat_sum = sum(row['total'] for row in vat_rows)
        assert total_vat_sum == Decimal("270.00")
        
        sums_dict = {row['category__code']: row for row in category_sums if row['category__code'] != "1155-00"}
        
        assert "5101-00" in sums_dict
        assert sums_dict["5101-00"]["total"] == Decimal("1430.00")
        
        assert "PV: PV-6902-001" in sums_dict
        assert sums_dict["PV: PV-6902-001"]["total"] == Decimal("300.00")
        
        # Verify unallocated count is 0 (since PV-6902-001 is excluded from unallocated items)
        assert response.context['unallocated_count'] == 0
        
        # Test searching inside summary view: filter by payee
        response_search = client.get(url, {'round_id': str(replenishment.id), 'sf': ['payee'], 'sv': ['Somchai']})
        assert response_search.status_code == 200
        category_sums_search = response_search.context['category_sums']
        search_sums_dict = {row['category__code']: row for row in category_sums_search if row['category__code'] != "1155-00"}
        assert "5101-00" in search_sums_dict
        assert search_sums_dict["5101-00"]["total"] == Decimal("930.00")

        # POST request to post the round's vouchers
        response_post = client.post(url, {'round_id': str(replenishment.id)})
        assert response_post.status_code == 302
        
        # Verify all payments are marked as posted
        pay_a.refresh_from_db()
        pay_b.refresh_from_db()
        pay_c.refresh_from_db()
        pay_d.refresh_from_db()
        assert pay_a.is_posted is True
        assert pay_b.is_posted is True
        assert pay_c.is_posted is True
        assert pay_d.is_posted is True

    def test_payment_with_rounding_adjustment(self, client, manager_user, account, company):
        client.force_login(manager_user)
        
        # Configure custom category codes on the account
        account.rounding_category_code = '4200-09'
        account.save()
        
        # Create rounding category
        cat_rounding = PettyCashCategory.objects.create(
            company=company,
            code="4200-09",
            name="Rounding Adjustments",
            created_by=manager_user
        )
        
        # Create standard expense category
        cat_expense = PettyCashCategory.objects.create(
            company=company,
            code="5101-00",
            name="Taxi fare",
            created_by=manager_user
        )
        
        # Capture initial balance
        account.refresh_from_db()
        initial_bal = account.balance
        
        # Create normal payment (Amount 1001.00 gross + Rounding 0.25)
        pay_expense = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=[{
                'description': 'Taxi fare',
                'amount': Decimal('1001.00'),
                'category': cat_expense,
                'note': '',
                'rounding_adjustment': Decimal('0.25')
            }],
            created_by=manager_user
        )
        
        # Verify disbursement total amount is exactly 1001.00 (the gross amount)
        assert pay_expense.total_amount == Decimal("1001.00")
        assert pay_expense.items.first().rounding_adjustment == Decimal("0.25")
        
        # Verify account balance decreased by 1001.00
        account.refresh_from_db()
        assert account.balance == initial_bal - Decimal("1001.00")
        
        # Verify that ONLY the standard expense item is created (count is 1)
        items = pay_expense.items.all()
        assert items.count() == 1
        
        expense_item = items.first()
        assert expense_item.amount == Decimal("1001.00")
        assert expense_item.category == cat_expense
        
        # Update the payment and verify it stays stable
        all_items_data = []
        for item in pay_expense.items.all():
            all_items_data.append({
                'category': item.category,
                'description': item.description,
                'amount': item.amount,
                'tax': item.tax,
                'note': item.note,
                'rounding_adjustment': Decimal("0.25")
            })
            
        updated_pay = PettyCashPaymentService.update_payment(
            pay_expense,
            updated_by=manager_user,
            items_data=all_items_data
        )
        assert updated_pay.total_amount == Decimal("1001.00")
        assert updated_pay.items.count() == 1
        
        # Create negative rounding payment (Amount 500.00 gross + Rounding -0.50)
        pay_expense_neg = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=[{
                'description': 'Office supplies',
                'amount': Decimal('500.00'),
                'category': cat_expense,
                'note': '',
                'rounding_adjustment': Decimal('-0.50')
            }],
            created_by=manager_user
        )

        # Create a replenishment to mark the end of the round
        replenishment = PettyCashPayment.objects.create(
            account=account,
            payment_type="replenishment",
            total_amount=Decimal("1501.00"),
            created_by=manager_user
        )
        
        # Verify summary page aggregates rounding item under 4200-09
        url = reverse('accounting:payment-summary', kwargs={'account_code': account.code})
        response = client.get(url, {'round_id': str(replenishment.id)})
        assert response.status_code == 200
        
        category_sums = response.context['category_sums']
        # Rounded adjustments are now individual rows instead of a single aggregated row.
        rounding_rows = [row for row in category_sums if row['category__code'] == "4200-09"]
        total_rounding_sum = sum(row['total'] for row in rounding_rows)
        assert total_rounding_sum == Decimal("-0.25")
        
        sums_dict = {row['category__code']: row for row in category_sums if row['category__code'] not in ("4200-09", "1155-00")}
        
        # Expense: (1001.00 - 0.25) + (500.00 - (-0.50)) = 1000.75 + 500.50 = 1501.25
        assert "5101-00" in sums_dict
        assert sums_dict["5101-00"]["total"] == Decimal("1501.25")
