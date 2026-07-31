from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounting.models import PettyCashPayment, PettyCashPaymentItem, PettyCashAccount


class PettyCashPaymentService:
    @staticmethod
    @transaction.atomic
    def create_payment(*, account, payment_type, items_data, payee=None, payee_name='', payment_date=None, created_by, note='', external_pv_no='', rounding_adjustment=None):
        """
        Create a new PettyCashPayment atomically, locking and updating account balance.
        items_data should be: [{'description': '...', 'amount': Decimal('...'), 'category': category_obj, 'note': '...'}]
        """
        if not items_data:
            raise ValidationError("A payment must contain at least one item line.")

        # Lock account
        locked_account = PettyCashAccount.objects.select_for_update().get(pk=account.pk)

        # Validate categories: company check and external PV rule
        for item in items_data:
            category = item.get('category')
            if external_pv_no and category is not None:
                raise ValidationError("Vouchers with an external PV number cannot have a Chart of Accounts category assigned.")
            if category and category.company != locked_account.company:
                raise ValidationError(
                    f"Category '{category.code}' belongs to company '{category.company.code}', "
                    f"which does not match the account's company '{locked_account.company.code}'."
                )

        # Handle rounding adjustment for disbursements and adjustments
        rounding_val = Decimal('0.00')
        rounding_cat = None
        if payment_type in ['disbursement', 'adjustment'] and rounding_adjustment:
            rounding_val = Decimal(str(rounding_adjustment))
            if rounding_val != Decimal('0.00'):
                rounding_code = locked_account.rounding_category_code or '4200-07'
                from accounting.models import PettyCashCategory
                rounding_cat = PettyCashCategory.objects.filter(
                    code=rounding_code,
                    company=locked_account.company,
                    is_deleted=False
                ).first()
                if not rounding_cat:
                    raise ValidationError(f"Rounding category with code '{rounding_code}' does not exist for company '{locked_account.company.code}'.")

        # Aggregate total amount
        # Aggregate total amount
        total_amount = sum(item['amount'] for item in items_data)

        # Update balance based on transaction type
        if payment_type == 'disbursement':
            if locked_account.balance < total_amount:
                raise ValidationError("Insufficient funds in the petty cash account.")
            locked_account.balance -= total_amount
        elif payment_type == 'replenishment':
            locked_account.balance += total_amount
        elif payment_type == 'adjustment':
            # Negative adjustment decreases balance, positive adjustment increases balance
            if total_amount < 0:
                abs_val = abs(total_amount)
                if locked_account.balance < abs_val:
                    raise ValidationError("Insufficient funds in the petty cash account for this negative adjustment.")
            locked_account.balance += total_amount
        else:
            raise ValidationError(f"Invalid payment type: {payment_type}")

        # Save account
        locked_account.save()

        # Create payment
        payment = PettyCashPayment(
            payment_type=payment_type,
            total_amount=total_amount,
            account=locked_account,
            payee=payee,
            payee_name=payee_name,
            created_by=created_by,
            note=note,
            external_pv_no=external_pv_no,
            rounding_adjustment=rounding_adjustment
        )
        if payment_date:
            payment.payment_date = payment_date
        payment.full_clean()
        payment.save()

        # Create items
        for item in items_data:
            line_item = PettyCashPaymentItem(
                payment=payment,
                description=item.get('description', ''),
                amount=item['amount'],
                tax=item.get('tax'),
                category=item.get('category'),
                note=item.get('note', '')
            )
            line_item.full_clean()
            line_item.save()

        return payment

    @staticmethod
    @transaction.atomic
    def cancel_payment(payment, *, user):
        """
        Cancel (soft-delete) a PettyCashPayment atomically, reversing its balance mutation on the account.
        """
        if payment.is_deleted:
            raise ValidationError("This payment is already cancelled.")
        if payment.is_posted:
            raise ValidationError("Cannot cancel a voucher that has already been posted to Express.")

        # Lock account
        locked_account = PettyCashAccount.objects.select_for_update().get(pk=payment.account.pk)

        # Reverse the balance change
        if payment.payment_type == 'disbursement':
            # Restore the funds
            locked_account.balance += payment.total_amount
        elif payment.payment_type == 'replenishment':
            # Remove the funds
            if locked_account.balance < payment.total_amount:
                raise ValidationError("Cannot cancel this replenishment because it would result in a negative account balance.")
            locked_account.balance -= payment.total_amount
        elif payment.payment_type == 'adjustment':
            # Reversing adjustment means subtracting what was added
            if locked_account.balance < payment.total_amount:
                raise ValidationError("Cannot cancel this adjustment because it would result in a negative account balance.")
            locked_account.balance -= payment.total_amount

        # Save account
        locked_account.save()

        # Soft-delete payment
        payment.delete(user=user)

    @staticmethod
    @transaction.atomic
    def update_payment(payment, *, updated_by, items_data=None, payee=None, payee_name='', payment_date=None, note='', external_pv_no=None, rounding_adjustment=None):
        """
        Update an existing PettyCashPayment. If items_data is provided, recalculate balance.
        """
        if payment.is_deleted:
            raise ValidationError("Cannot update a cancelled payment.")
        if payment.is_posted:
            raise ValidationError("Cannot update a voucher that has already been posted to Express.")

        # Lock account
        locked_account = PettyCashAccount.objects.select_for_update().get(pk=payment.account.pk)

        # Update allowed non-financial fields on the model directly
        payment.payee = payee
        payment.payee_name = payee_name.strip() if payee_name else ''
        payment.note = note
        if payment_date:
            payment.payment_date = payment_date
        if external_pv_no is not None:
            payment.external_pv_no = external_pv_no
        if rounding_adjustment is not None:
            payment.rounding_adjustment = rounding_adjustment

        effective_external_pv = payment.external_pv_no

        if items_data is not None:
            if not items_data:
                raise ValidationError("A payment must contain at least one item line.")

            # Validate all categories belong to the same company
            for item in items_data:
                category = item.get('category')
                if effective_external_pv and category is not None:
                    raise ValidationError("Vouchers with an external PV number cannot have a Chart of Accounts category assigned.")
                if category and category.company != locked_account.company:
                    raise ValidationError(
                        f"Category '{category.code}' belongs to company '{category.company.code}', "
                        f"which does not match the account's company '{locked_account.company.code}'."
                    )

            # Recalculate amount
            new_total_amount = sum(item['amount'] for item in items_data)
            diff = new_total_amount - payment.total_amount

            # Update account balance based on payment_type and diff
            if payment.payment_type == 'disbursement':
                # Disbursement decreases balance, so positive diff means we need more funds
                if locked_account.balance < diff:
                    raise ValidationError("Insufficient funds in the petty cash account for this update.")
                locked_account.balance -= diff
            elif payment.payment_type == 'replenishment':
                # Replenishment increases balance, so positive diff means we add more funds
                if locked_account.balance + diff < 0:
                    raise ValidationError("Cannot update this replenishment because it would result in a negative account balance.")
                locked_account.balance += diff
            elif payment.payment_type == 'adjustment':
                if locked_account.balance + diff < 0:
                    raise ValidationError("Cannot update this adjustment because it would result in a negative account balance.")
                locked_account.balance += diff

            # Update total amount on payment
            payment.total_amount = new_total_amount

            # Save account
            locked_account.save()

            # Replace items
            payment.items.all().delete()
            for item in items_data:
                line_item = PettyCashPaymentItem(
                    payment=payment,
                    description=item.get('description', ''),
                    amount=item['amount'],
                    tax=item.get('tax'),
                    category=item.get('category'),
                    note=item.get('note', '')
                )
                line_item.full_clean()
                line_item.save()
        else:
            # If items_data is not updated, but external_pv_no is being set to a non-empty value:
            if effective_external_pv:
                if payment.items.filter(category__isnull=False).exists():
                    raise ValidationError("Cannot assign an external PV number to a voucher that has Chart of Accounts categories allocated.")

        payment.updated_by = updated_by
        payment.full_clean()
        payment.save()
        return payment

    @staticmethod
    @transaction.atomic
    def mark_payments_as_posted(payments, *, user):
        """
        Mark a list of PettyCashPayment records as posted to Express ERP.
        Ensure all items have categories assigned.
        """
        for payment in payments:
            if payment.is_deleted:
                raise ValidationError(f"Voucher {payment.payment_no} is cancelled and cannot be posted.")
            if payment.is_posted:
                continue
            
            # Verify all items have a category, unless it is an external PV payment
            if not payment.external_pv_no:
                for item in payment.items.all():
                    if not item.category:
                        raise ValidationError(f"Voucher {payment.payment_no} has unallocated line items (missing category).")
            
            payment.is_posted = True
            payment.posted_at = timezone.now()
            payment.posted_by = user
            payment.save()
