"""
Tests for Partner Model

Tests cover:
- Basic CRUD
- Unique Name and Code constraints
- Field normalization (strip whitespace, uppercase code)
- Role flags (is_supplier, is_customer)
- Inherited mixin behaviour (audit, status, soft delete)
"""

import pytest
from django.db import IntegrityError
from django.contrib.auth.models import User
from partners.models import Partner

# ---------- Fixtures ----------
@pytest.fixture
def admin_user(db):
    """Create a test user for auditable fields."""
    return User.objects.create_user(
        username="admin", 
        password="admin123", 
        is_staff=True,
    )

@pytest.fixture
def partner_supplier(db, admin_user):
    """Create a supplier partner."""
    return Partner.objects.create(
        name="Global Supplier Co.",
        code="SUP-001",
        is_supplier=True,
        created_by=admin_user,
    )

@pytest.fixture
def partner_customer(db, admin_user):
    """Create a customer partner."""
    return Partner.objects.create(
        name="Large Customer Ltd.",
        code="CUST-001",
        is_customer=True,
        created_by=admin_user,
    )

# ============================================================
# Basic CRUD
# ============================================================
@pytest.mark.unit
class TestPartnerCRUD:

    def test_create_partner(self, partner_supplier):
        assert partner_supplier.pk is not None
        assert partner_supplier.name == "Global Supplier Co."
        assert partner_supplier.code == "SUP-001"
        assert partner_supplier.is_supplier is True
        assert partner_supplier.is_customer is False

    def test_str_representation(self, partner_supplier):
        assert str(partner_supplier) == "SUP-001 - Global Supplier Co."

    def test_update_partner_details(self, partner_supplier):
        partner_supplier.contact_name = "Alice Smith"
        partner_supplier.save()
        partner_supplier.refresh_from_db()
        assert partner_supplier.contact_name == "Alice Smith"

    def test_optional_fields_defaults(self, partner_supplier):
        assert partner_supplier.tax_id == ''
        assert partner_supplier.address == ''
        assert partner_supplier.email == ''

# ============================================================
# Constraints & Business Logic
# ============================================================
@pytest.mark.unit
class TestPartnerConstraints:

    def test_duplicate_name_raises_error(self, partner_supplier, admin_user):
        with pytest.raises(IntegrityError):
            Partner.objects.create(
                name="Global Supplier Co.",
                code="SUP-DIFF",
                created_by=admin_user,
            )

    def test_duplicate_code_raises_error(self, partner_supplier, admin_user):
        with pytest.raises(IntegrityError):
            Partner.objects.create(
                name="Different Name",
                code="SUP-001",
                created_by=admin_user,
            )

    def test_multi_role_partner(self, db, admin_user):
        """A partner can be both supplier and customer."""
        partner = Partner.objects.create(
            name="Hybrid Partner",
            code="HYB-01",
            is_supplier=True,
            is_customer=True,
            created_by=admin_user,
        )
        assert partner.is_supplier is True
        assert partner.is_customer is True

# ============================================================
# Field Normalization
# ============================================================
@pytest.mark.unit
class TestFieldNormalization:

    def test_name_and_code_normalization(self, admin_user):
        """Check stripping and uppercasing."""
        partner = Partner.objects.create(
            name="   Messy Name   ",
            code="  low-code-01  ",
            created_by=admin_user,
        )
        assert partner.name == "Messy Name"
        assert partner.code == "LOW-CODE-01"

# ============================================================
# Inherited Mixin Behaviour
# ============================================================
@pytest.mark.unit
class TestPartnerMixins:

    def test_audit_fields_set(self, partner_supplier, admin_user):
        assert partner_supplier.created_at is not None
        assert partner_supplier.created_by == admin_user
        assert partner_supplier.updated_at is not None

    def test_default_status_active(self, partner_supplier):
        assert partner_supplier.status == Partner.Status.ACTIVE
        assert partner_supplier.is_active is True

    def test_deactivate_partner(self, partner_supplier):
        partner_supplier.deactivate()
        partner_supplier.refresh_from_db()
        assert partner_supplier.is_active is False

    def test_soft_delete_partner(self, partner_supplier, admin_user):
        partner_supplier.delete(user=admin_user)
        partner_supplier.refresh_from_db()
        assert partner_supplier.is_deleted is True
        assert partner_supplier.deleted_at is not None
        assert partner_supplier.deleted_by == admin_user

    def test_optimistic_locking_version(self, partner_supplier):
        assert partner_supplier.version == 1
        partner_supplier.name = "New Name"
        partner_supplier.save()
        assert partner_supplier.version == 2
