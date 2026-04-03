import pytest
from django.urls import reverse
from django.contrib.auth.models import User
from partners.models import Partner

@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("admin", "admin@test.com", "pass")

@pytest.fixture
def partner(db, admin_user):
    return Partner.objects.create(
        name="Test Supplier", code="TEST-SUP", is_supplier=True, created_by=admin_user
    )

@pytest.mark.django_db
class TestPartnerListView:
    """Functional tests for the Partner List view."""

    def test_partner_list_view_status_code(self, client, admin_user, partner):
        client.force_login(admin_user)
        # Add permission
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(codename='view_partner')
        admin_user.user_permissions.add(perm)
        
        url = reverse('partners:partner-list')
        response = client.get(url)
        assert response.status_code == 200
        assert "Test Supplier" in response.content.decode()

    def test_partner_list_view_filter(self, client, admin_user, partner):
        client.force_login(admin_user)
        from django.contrib.auth.models import Permission
        perm = Permission.objects.get(codename='view_partner')
        admin_user.user_permissions.add(perm)
        
        # Create a customer
        Partner.objects.create(name="Only Customer", code="CUST-1", is_customer=True, created_by=admin_user)
        
        url = reverse('partners:partner-list')
        
        # Filter for suppliers
        response = client.get(url + '?role=supplier')
        assert "Test Supplier" in response.content.decode()
        assert "Only Customer" not in response.content.decode()
