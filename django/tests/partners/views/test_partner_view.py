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
        
        content = response.content.decode()
        assert "Test Supplier" in content
        assert "TEST-SUP" in content
        assert "Supplier" in content

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
        content = response.content.decode()
        assert "Test Supplier" in content
        assert "Only Customer" not in content

    def test_partner_with_spaces_in_code(self, client, admin_user):
        """Verify that partner codes with spaces (now str:code) work for routing."""
        client.force_login(admin_user)
        from django.contrib.auth.models import Permission
        for pc in ['view_partner', 'change_partner']:
            perm = Permission.objects.get(codename=pc)
            admin_user.user_permissions.add(perm)
            
        partner_with_space = Partner.objects.create(
            name="Partner With Space", 
            code="SUP 001", 
            is_supplier=True, 
            created_by=admin_user
        )
        
        # Test Detail View
        detail_url = reverse('partners:partner-detail', kwargs={'code': 'SUP 001'})
        response = client.get(detail_url)
        assert response.status_code == 200
        assert "Partner With Space" in response.content.decode()
        
        # Test Update View
        update_url = reverse('partners:partner-update', kwargs={'code': 'SUP 001'})
        response = client.get(update_url)
        assert response.status_code == 200
