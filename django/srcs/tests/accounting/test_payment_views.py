import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from django.utils import timezone
from common.models import Company, Individual
from accounting.models import PettyCashAccount, PettyCashCategory, PettyCashPayment, PettyCashPaymentItem

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
        
        # Check GET summary page
        url = reverse('accounting:payment-summary', kwargs={'account_code': account.code})
        response = client.get(url)
        assert response.status_code == 200
        assert len(response.context['category_sums']) == 1
        assert response.context['unallocated_count'] == 0
        
        # Post the month's vouchers
        post_data = {
            'year': str(timezone.now().year),
            'month': str(timezone.now().month)
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
        
        url = reverse('accounting:payment-summary', kwargs={'account_code': account.code})
        post_data = {
            'year': str(timezone.now().year),
            'month': str(timezone.now().month)
        }
        response = client.post(url, post_data)
        assert response.status_code == 302
        
        # Verify payment status is still unposted due to validation failure
        unallocated_payment.refresh_from_db()
        assert unallocated_payment.is_posted is False
