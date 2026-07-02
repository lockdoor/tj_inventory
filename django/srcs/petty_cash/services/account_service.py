from django.core.exceptions import ValidationError
from petty_cash.models import PettyCashAccount


class PettyCashAccountService:
    @staticmethod
    def create_account(*, code, name, max_limit, company, custodian, created_by, note=''):
        """
        Create a new PettyCashAccount.
        """
        account = PettyCashAccount(
            code=code,
            name=name,
            max_limit=max_limit,
            company=company,
            custodian=custodian,
            created_by=created_by,
            note=note
        )
        account.full_clean()
        account.save()
        return account

    @staticmethod
    def update_account(account, *, updated_by, **fields):
        """
        Update an existing PettyCashAccount.
        """
        allowed_fields = {'code', 'name', 'max_limit', 'currency', 'status', 'custodian', 'note'}

        # custodian can not update 
        if 'custodian' in fields and fields['custodian'] != account.custodian:
            raise ValidationError("Custodian can not update.")
            
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(account, field, value)
        account.updated_by = updated_by
        account.full_clean()
        account.save()
        return account

    @staticmethod
    def soft_delete_account(account, *, user):
        """
        Soft-delete a PettyCashAccount.
        """
        # Ensure it's not referenced by active payments
        if account.payments.filter(is_deleted=False).exists():
            raise ValidationError("Cannot delete account because it contains active payments.")
        account.delete(user=user)

    @staticmethod
    def restore_account(account, *, user):
        """
        Restore a soft-deleted PettyCashAccount.
        """
        account.restore(user=user)
        return account
