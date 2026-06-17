"""
Partner Service

Business logic for Partner operations.
Handles rules that go beyond simple data integrity.
"""

from django.core.exceptions import ValidationError
from partners.models import Partner


class PartnerService:

    @staticmethod
    def get_active_queryset():
        """
        Return a base queryset of non-deleted partners.
        """
        return Partner.objects.filter(is_deleted=False)

    @staticmethod
    def list_active():
        """
        Return all active (non-deleted) partners ordered by name.
        """
        return PartnerService.get_active_queryset().order_by('name')

    @staticmethod
    def list_deleted():
        """
        Return all soft-deleted partners ordered by name.
        """
        return Partner.objects.filter(is_deleted=True).order_by('name')

    @staticmethod
    def list_suppliers():
        """
        Return active partners that are suppliers.
        """
        return PartnerService.get_active_queryset().filter(is_supplier=True).order_by('name')

    @staticmethod
    def list_customers():
        """
        Return active partners that are customers.
        """
        return PartnerService.get_active_queryset().filter(is_customer=True).order_by('name')

    @staticmethod
    def create(*, name, code, user, is_supplier=False, is_customer=False, **extra_fields):
        """
        Create a new partner.
        """
        partner = Partner(
            name=name,
            code=code,
            is_supplier=is_supplier,
            is_customer=is_customer,
            created_by=user,
            **extra_fields
        )
        partner.full_clean()
        partner.save()
        return partner

    @staticmethod
    def update(partner, *, user, **fields):
        """
        Update an existing partner.
        """
        allowed_fields = {
            'name', 'code', 'is_supplier', 'is_customer', 
            'tax_id', 'address', 'contact_name', 'phone', 
            'email', 'note', 'status'
        }
        
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(partner, field, value)

        partner.updated_by = user
        partner.full_clean()
        partner.save()
        return partner

    @staticmethod
    def soft_delete(partner, *, user):
        """
        Soft-delete a partner.
        """
        partner.delete(user=user)

    @staticmethod
    def restore(partner, *, user):
        """
        Restore a soft-deleted partner.
        """
        partner.restore(user=user)
        return partner
