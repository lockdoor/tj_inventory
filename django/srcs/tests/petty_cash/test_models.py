import pytest
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from common.models import Company, Individual
from petty_cash.models import (
    PettyCashCategory,
    PettyCashAccount,
    PettyCashPayment,
    PettyCashPaymentItem,
    PettyCashPaymentAttachment
)


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("admin", "admin@test.com", "pass")


@pytest.fixture
def company(db, admin_user):
    return Company.objects.create(
        code="TJ",
        name="TJ Company",
        created_by=admin_user
    )


@pytest.fixture
def payee(db, admin_user):
    return Individual.objects.create(
        first_name_th="สมชาย",
        last_name_th="ดีใจ",
        created_by=admin_user
    )


@pytest.fixture
def petty_cash_account(db, company, admin_user):
    return PettyCashAccount.objects.create(
        code="pc-tj",
        name="TJ Main Cash Box",
        max_limit=Decimal("5000.00"),
        balance=Decimal("2000.00"),
        company=company,
        custodian=admin_user,
        created_by=admin_user
    )


@pytest.fixture
def petty_cash_category(db, company, admin_user):
    return PettyCashCategory.objects.create(
        code="5101-01",
        name="Travel Expenses",
        company=company,
        created_by=admin_user
    )


@pytest.mark.django_db
class TestPettyCashModels:
    """
    Unit tests for the petty cash app database models.
    """

    def test_category_creation_and_constraints(self, company, admin_user):
        cat = PettyCashCategory.objects.create(
            code="  5102-02  ",
            name="  Office Supplies  ",
            company=company,
            created_by=admin_user
        )
        assert cat.code == "5102-02"
        assert cat.name == "Office Supplies"
        assert str(cat) == "5102-02 - Office Supplies"

        # Unique together constraint test (company + code)
        with pytest.raises(IntegrityError):
            PettyCashCategory.objects.create(
                code="5102-02",
                name="Duplicate Code",
                company=company,
                created_by=admin_user
            )

    def test_account_creation_and_normalizations(self, company, admin_user):
        acc = PettyCashAccount.objects.create(
            code="  pc-tj-new  ",
            name="  New Cash Box  ",
            max_limit=Decimal("10000.00"),
            company=company,
            custodian=admin_user,
            created_by=admin_user
        )
        assert acc.code == "PC-TJ-NEW"
        assert acc.name == "New Cash Box"
        assert acc.balance == Decimal("0.00")
        assert acc.currency == "THB"
        assert acc.status == "active"
        assert str(acc) == "PC-TJ-NEW - New Cash Box (admin)"

    def test_payment_and_voucher_auto_generation(self, petty_cash_account, payee, admin_user):
        payment1 = PettyCashPayment.objects.create(
            payment_type="disbursement",
            account=petty_cash_account,
            payee=payee,
            created_by=admin_user
        )
        
        date_str = timezone.now().strftime('%Y%m%d')
        # Voucher number should match sequence
        assert payment1.payment_no == f"PV-{date_str}-0001"
        assert payment1.payee_name == ""

        payment2 = PettyCashPayment.objects.create(
            payment_type="disbursement",
            account=petty_cash_account,
            payee_name="  One-Time Payee  ",
            created_by=admin_user
        )
        assert payment2.payment_no == f"PV-{date_str}-0002"
        assert payment2.payee_name == "One-Time Payee"

    def test_payment_item_creation(self, petty_cash_account, petty_cash_category, admin_user):
        payment = PettyCashPayment.objects.create(
            payment_type="disbursement",
            account=petty_cash_account,
            created_by=admin_user
        )
        item = PettyCashPaymentItem.objects.create(
            payment=payment,
            description="Fuel for delivery truck",
            amount=Decimal("150.50"),
            category=petty_cash_category
        )
        assert item.payment == payment
        assert item.amount == Decimal("150.50")
        assert item.category == petty_cash_category
        assert str(item) == f"{payment.payment_no} Line Item: Travel Expenses - 150.50"

    def test_payment_attachment_creation(self, petty_cash_account, admin_user):
        payment = PettyCashPayment.objects.create(
            payment_type="disbursement",
            account=petty_cash_account,
            created_by=admin_user
        )
        attachment = PettyCashPaymentAttachment.objects.create(
            payment=payment,
            document_file="test_receipt.pdf",
            note="Gas receipt",
            created_by=admin_user
        )
        assert attachment.payment == payment
        assert attachment.file_name == "test_receipt.pdf"
        assert str(attachment) == f"{payment.payment_no} - test_receipt.pdf"
