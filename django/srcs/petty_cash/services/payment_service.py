from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from petty_cash.models import PettyCashPayment, PettyCashPaymentItem, PettyCashAccount


class PettyCashPaymentService:
    @staticmethod
    @transaction.atomic
    def create_payment(*, account, payment_type, items_data, payee=None, payee_name='', payment_date=None, created_by, note=''):
        """
        Create a new PettyCashPayment atomically, locking and updating account balance.
        items_data should be: [{'description': '...', 'amount': Decimal('...'), 'category': category_obj, 'note': '...'}]
        """
        if not items_data:
            raise ValidationError("A payment must contain at least one item line.")

        # Lock account
        locked_account = PettyCashAccount.objects.select_for_update().get(pk=account.pk)

        # Validate all categories belong to the same company
        for item in items_data:
            category = item['category']
            if category.company != locked_account.company:
                raise ValidationError(
                    f"Category '{category.code}' belongs to company '{category.company.code}', "
                    f"which does not match the account's company '{locked_account.company.code}'."
                )

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
            note=note
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
                category=item['category'],
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
    def update_payment(payment, *, updated_by, items_data=None, payee=None, payee_name='', payment_date=None, note=''):
        """
        Update an existing PettyCashPayment. If items_data is provided, recalculate balance.
        """
        if payment.is_deleted:
            raise ValidationError("Cannot update a cancelled payment.")

        # Lock account
        locked_account = PettyCashAccount.objects.select_for_update().get(pk=payment.account.pk)

        # Update allowed non-financial fields on the model directly
        payment.payee = payee
        payment.payee_name = payee_name.strip() if payee_name else ''
        payment.note = note
        if payment_date:
            payment.payment_date = payment_date

        if items_data is not None:
            if not items_data:
                raise ValidationError("A payment must contain at least one item line.")

            # Validate all categories belong to the same company
            for item in items_data:
                category = item['category']
                if category.company != locked_account.company:
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
                    category=item['category'],
                    note=item.get('note', '')
                )
                line_item.full_clean()
                line_item.save()

        payment.updated_by = updated_by
        payment.full_clean()
        payment.save()
        return payment
