import pytest
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import transaction
from common.models import Company, Individual
from accounting.models import (
    PettyCashCategory,
    PettyCashAccount,
    PettyCashPayment,
    PettyCashPaymentItem
)
from accounting.services import (
    PettyCashCategoryService,
    PettyCashAccountService,
    PettyCashPaymentService
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
def other_company(db, admin_user):
    return Company.objects.create(
        code="OTHER",
        name="Other Company",
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
def account(db, company, admin_user):
    return PettyCashAccountService.create_account(
        code="PC-TJ",
        name="TJ Main Cash Box",
        max_limit=Decimal("5000.00"),
        company=company,
        custodian=admin_user,
        created_by=admin_user,
        note="Initial account note"
    )


@pytest.fixture
def category(db, company, admin_user):
    return PettyCashCategoryService.create_category(
        code="5101-01",
        name="Travel",
        company=company,
        created_by=admin_user,
        note="Initial category note"
    )


@pytest.mark.django_db
class TestPettyCashServices:

    def test_category_service_crud(self, company, admin_user):
        # Create
        cat = PettyCashCategoryService.create_category(
            code="5102-02",
            name="Supplies",
            company=company,
            created_by=admin_user,
            note="Test note"
        )
        assert cat.code == "5102-02"
        assert cat.note == "Test note"

        # Update
        updated = PettyCashCategoryService.update_category(
            cat,
            updated_by=admin_user,
            name="Office Supplies",
            note="Updated note"
        )
        assert updated.name == "Office Supplies"
        assert updated.note == "Updated note"

        # Soft Delete
        PettyCashCategoryService.soft_delete_category(updated, user=admin_user)
        updated.refresh_from_db()
        assert updated.is_deleted is True

        # Restore
        PettyCashCategoryService.restore_category(updated, user=admin_user)
        updated.refresh_from_db()
        assert updated.is_deleted is False

    def test_account_service_crud(self, company, admin_user):
        # Create
        acc = PettyCashAccountService.create_account(
            code="PC-TEST",
            name="Test Account",
            max_limit=Decimal("1000.00"),
            company=company,
            custodian=admin_user,
            created_by=admin_user,
            note="Acc note"
        )
        assert acc.code == "PC-TEST"
        assert acc.balance == Decimal("0.00")

        # Update
        updated = PettyCashAccountService.update_account(
            acc,
            updated_by=admin_user,
            name="Updated Account Name",
            note="Updated acc note"
        )
        assert updated.name == "Updated Account Name"
        assert updated.note == "Updated acc note"

        # Test changing custodian is blocked
        another_user = User.objects.create_user("another_custodian", "another@test.com", "pass")
        with pytest.raises(ValidationError, match="Custodian can not update"):
            PettyCashAccountService.update_account(
                updated,
                updated_by=admin_user,
                custodian=another_user
            )

        # Soft Delete
        PettyCashAccountService.soft_delete_account(updated, user=admin_user)
        updated.refresh_from_db()
        assert updated.is_deleted is True

        # Restore
        PettyCashAccountService.restore_account(updated, user=admin_user)
        updated.refresh_from_db()
        assert updated.is_deleted is False

    def test_payment_creation_and_balance_mutations(self, account, category, admin_user, payee):
        # Initialize account balance via replenishment
        replenishment_data = [
            {'description': 'Initial replenishment', 'amount': Decimal("2000.00"), 'category': category}
        ]
        payment_rep = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="replenishment",
            items_data=replenishment_data,
            created_by=admin_user,
            note="Replenish note"
        )
        account.refresh_from_db()
        assert account.balance == Decimal("2000.00")
        assert payment_rep.total_amount == Decimal("2000.00")
        assert payment_rep.note == "Replenish note"

        # Create disbursement
        disbursement_data = [
            {'description': 'Taxi fare', 'amount': Decimal("150.00"), 'category': category},
            {'description': 'Dinner client', 'amount': Decimal("350.00"), 'category': category, 'note': 'Line note'}
        ]
        payment_dis = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=disbursement_data,
            payee=payee,
            created_by=admin_user
        )
        account.refresh_from_db()
        assert account.balance == Decimal("1500.00")
        assert payment_dis.total_amount == Decimal("500.00")

    def test_insufficient_funds_validation(self, account, category, admin_user):
        account.balance = Decimal("100.00")
        account.save()

        items = [{'description': 'Expense', 'amount': Decimal("150.00"), 'category': category}]
        with pytest.raises(ValidationError, match="Insufficient funds"):
            PettyCashPaymentService.create_payment(
                account=account,
                payment_type="disbursement",
                items_data=items,
                created_by=admin_user
            )
        
        # Verify balance remains unchanged
        account.refresh_from_db()
        assert account.balance == Decimal("100.00")

    def test_category_company_mismatch_validation(self, account, other_company, admin_user):
        other_cat = PettyCashCategoryService.create_category(
            code="MISMATCH",
            name="Mismatch",
            company=other_company,
            created_by=admin_user
        )
        items = [{'description': 'Expense', 'amount': Decimal("10.00"), 'category': other_cat}]
        with pytest.raises(ValidationError, match="belongs to company 'OTHER'"):
            PettyCashPaymentService.create_payment(
                account=account,
                payment_type="disbursement",
                items_data=items,
                created_by=admin_user
            )

    def test_payment_cancellation_and_balance_reversal(self, account, category, admin_user):
        # Set base balance
        account.balance = Decimal("1000.00")
        account.save()

        # 1. Create disbursement of 200
        dis_items = [{'description': 'Expense', 'amount': Decimal("200.00"), 'category': category}]
        payment = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=dis_items,
            created_by=admin_user
        )
        account.refresh_from_db()
        assert account.balance == Decimal("800.00")

        # 2. Cancel disbursement (should add 200 back to balance)
        PettyCashPaymentService.cancel_payment(payment, user=admin_user)
        account.refresh_from_db()
        assert account.balance == Decimal("1000.00")
        payment.refresh_from_db()
        assert payment.is_deleted is True

    def test_cancel_replenishment_negative_balance_guard(self, account, category, admin_user):
        # 1. Replenish 1000
        rep_items = [{'description': 'Replenish', 'amount': Decimal("1000.00"), 'category': category}]
        payment = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="replenishment",
            items_data=rep_items,
            created_by=admin_user
        )
        account.refresh_from_db()
        assert account.balance == Decimal("1000.00")

        # 2. Spend 500 (balance drops to 500)
        dis_items = [{'description': 'Spend', 'amount': Decimal("500.00"), 'category': category}]
        PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=dis_items,
            created_by=admin_user
        )
        account.refresh_from_db()
        assert account.balance == Decimal("500.00")

        # 3. Try to cancel replenishment of 1000 (would drop balance to -500)
        with pytest.raises(ValidationError, match="would result in a negative account balance"):
            PettyCashPaymentService.cancel_payment(payment, user=admin_user)

        # Verify balance remains unchanged
        account.refresh_from_db()
        assert account.balance == Decimal("500.00")

    def test_payment_update_non_financial_fields(self, account, category, admin_user, payee):
        account.balance = Decimal("1000.00")
        account.save()

        items = [{'description': 'Expense', 'amount': Decimal("100.00"), 'category': category}]
        payment = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=items,
            created_by=admin_user
        )
        # Update payee and note
        updated_payment = PettyCashPaymentService.update_payment(
            payment,
            updated_by=admin_user,
            payee=payee,
            note="Updated payment note"
        )
        assert updated_payment.payee == payee
        assert updated_payment.note == "Updated payment note"
        assert updated_payment.total_amount == Decimal("100.00")

    def test_payment_update_financial_disbursement(self, account, category, admin_user):
        account.balance = Decimal("1000.00")
        account.save()

        items = [{'description': 'Expense', 'amount': Decimal("200.00"), 'category': category}]
        payment = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=items,
            created_by=admin_user
        )
        account.refresh_from_db()
        assert account.balance == Decimal("800.00")

        # 1. Update disbursement amount to 500 (increases disbursement, balance drops by 300 more)
        new_items = [{'description': 'Expense', 'amount': Decimal("500.00"), 'category': category}]
        PettyCashPaymentService.update_payment(
            payment,
            updated_by=admin_user,
            items_data=new_items
        )
        account.refresh_from_db()
        assert account.balance == Decimal("500.00")

        # 2. Update disbursement amount to 100 (decreases disbursement, balance increases by 400)
        newer_items = [{'description': 'Expense', 'amount': Decimal("100.00"), 'category': category}]
        PettyCashPaymentService.update_payment(
            payment,
            updated_by=admin_user,
            items_data=newer_items
        )
        account.refresh_from_db()
        assert account.balance == Decimal("900.00")

        # 3. Insufficient funds update test
        expensive_items = [{'description': 'Expense', 'amount': Decimal("2000.00"), 'category': category}]
        with pytest.raises(ValidationError, match="Insufficient funds"):
            PettyCashPaymentService.update_payment(
                payment,
                updated_by=admin_user,
                items_data=expensive_items
            )

    def test_payment_creation_and_update_with_tax(self, account, category, admin_user):
        account.balance = Decimal("1000.00")
        account.save()

        # 1. Create disbursement with tax
        items = [{'description': 'Expense with tax', 'amount': Decimal("200.00"), 'tax': Decimal("14.00"), 'category': category}]
        payment = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=items,
            created_by=admin_user
        )
        account.refresh_from_db()
        # 1000.00 - 200.00 = 800.00
        assert payment.total_amount == Decimal("200.00")
        assert account.balance == Decimal("800.00")

        # 2. Update disbursement with tax (changing tax and amount)
        new_items = [{'description': 'Expense with tax', 'amount': Decimal("300.00"), 'tax': Decimal("21.00"), 'category': category}]
        PettyCashPaymentService.update_payment(
            payment,
            updated_by=admin_user,
            items_data=new_items
        )
        account.refresh_from_db()
        # 1000.00 - 300.00 = 700.00
        assert payment.total_amount == Decimal("300.00")
        assert account.balance == Decimal("700.00")

    def test_payment_with_external_pv_constraints(self, account, category, admin_user):
        account.balance = Decimal("1000.00")
        account.save()

        # 1. Creating with external PV and a category should fail
        items = [{'description': 'Expense', 'amount': Decimal("100.00"), 'category': category}]
        with pytest.raises(ValidationError, match="Vouchers with an external PV number cannot have a Chart of Accounts category assigned."):
            PettyCashPaymentService.create_payment(
                account=account,
                payment_type="disbursement",
                items_data=items,
                created_by=admin_user,
                external_pv_no="EXT-PV-0001"
            )

        # 2. Creating with external PV and NO category should succeed
        items_no_cat = [{'description': 'Expense', 'amount': Decimal("100.00"), 'category': None}]
        payment = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=items_no_cat,
            created_by=admin_user,
            external_pv_no="EXT-PV-0001"
        )
        assert payment.external_pv_no == "EXT-PV-0001"

        # 3. Updating an external PV payment with a category should fail
        with pytest.raises(ValidationError, match="Vouchers with an external PV number cannot have a Chart of Accounts category assigned."):
            PettyCashPaymentService.update_payment(
                payment,
                updated_by=admin_user,
                items_data=items
            )

        # 4. Updating a payment with no category to have external PV should succeed
        payment2 = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=items_no_cat,
            created_by=admin_user
        )
        PettyCashPaymentService.update_payment(
            payment2,
            updated_by=admin_user,
            external_pv_no="EXT-PV-0002"
        )
        assert payment2.external_pv_no == "EXT-PV-0002"

        # 5. Setting external PV on a payment with a category should fail
        payment3 = PettyCashPaymentService.create_payment(
            account=account,
            payment_type="disbursement",
            items_data=items,
            created_by=admin_user
        )
        with pytest.raises(ValidationError, match="Cannot assign an external PV number to a voucher that has Chart of Accounts categories allocated."):
            PettyCashPaymentService.update_payment(
                payment3,
                updated_by=admin_user,
                external_pv_no="EXT-PV-0003"
            )
