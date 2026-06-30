from django.core.exceptions import ValidationError
from common.models import Company


class CompanyService:

    @staticmethod
    def get_active_queryset():
        """
        Return a base queryset of non-deleted companies.
        """
        return Company.objects.filter(is_deleted=False)

    @staticmethod
    def list_active():
        """
        Return all active (non-deleted) companies ordered by name.
        """
        return CompanyService.get_active_queryset().order_by('name')

    @staticmethod
    def list_deleted():
        """
        Return all soft-deleted companies ordered by name.
        """
        return Company.objects.filter(is_deleted=True).order_by('name')

    @staticmethod
    def create(*, name, code, user, express_database_name='', **extra_fields):
        """
        Create a new company.
        """
        company = Company(
            name=name,
            code=code,
            express_database_name=express_database_name,
            created_by=user,
            **extra_fields
        )
        company.full_clean()
        company.save()
        return company

    @staticmethod
    def update(company, *, user, **fields):
        """
        Update an existing company.
        """
        allowed_fields = {
            'name', 'code', 'express_database_name', 'tax_id', 
            'address', 'phone', 'email', 'note', 'status'
        }
        
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(company, field, value)

        company.updated_by = user
        company.full_clean()
        company.save()
        return company

    @staticmethod
    def soft_delete(company, *, user):
        """
        Soft-delete a company. Prevents deletion if referenced by active warehouses.
        """
        if company.warehouses.filter(is_deleted=False).exists():
            raise ValidationError("Cannot delete company because it is referenced by active warehouses.")
        company.delete(user=user)

    @staticmethod
    def restore(company, *, user):
        """
        Restore a soft-deleted company.
        """
        company.restore(user=user)
        return company
