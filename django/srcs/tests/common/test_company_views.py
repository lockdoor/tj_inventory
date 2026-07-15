import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from common.models import Company
from inventory.models import Warehouse

@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser("admin", "admin@test.com", "pass")
    # Grant all company permissions
    perms = Permission.objects.filter(codename__endswith='_company')
    user.user_permissions.add(*perms)
    return user

@pytest.fixture
def company(db, admin_user):
    return Company.objects.create(
        name="Test Company", 
        code="TEST001", 
        express_database_name="TESTDB",
        created_by=admin_user
    )

@pytest.fixture
def unauthorized_user(db):
    """User with no permissions."""
    return User.objects.create_user("plain_user", "plain@test.com", "pass")

@pytest.mark.django_db
class TestCompanyPermissions:
    """Security tests verifying that unauthorized users are denied access (403)."""

    def test_list_denied(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('common:company-list')
        response = client.get(url)
        assert response.status_code == 403

    def test_create_denied(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('common:company-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_update_denied(self, client, unauthorized_user, company):
        client.force_login(unauthorized_user)
        url = reverse('common:company-update', kwargs={'code': company.code})
        response = client.get(url)
        assert response.status_code == 403

    def test_delete_denied(self, client, unauthorized_user, company):
        client.force_login(unauthorized_user)
        url = reverse('common:company-delete', kwargs={'code': company.code})
        response = client.post(url)
        assert response.status_code == 403

    def test_trash_denied(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('common:company-trash')
        response = client.get(url)
        assert response.status_code == 403

    def test_restore_denied(self, client, unauthorized_user, company):
        client.force_login(unauthorized_user)
        company.is_deleted = True
        company.save()
        
        url = reverse('common:company-restore', kwargs={'code': company.code})
        response = client.post(url)
        assert response.status_code == 403

@pytest.mark.django_db
class TestCompanyCRUD:
    """Functional tests for Company Create, Update, Detail, Delete, and Restore."""

    def test_company_list_view(self, client, admin_user, company):
        client.force_login(admin_user)
        url = reverse('common:company-list')
        response = client.get(url)
        assert response.status_code == 200
        assert company.name in response.content.decode()

    def test_company_detail_view(self, client, admin_user, company):
        client.force_login(admin_user)
        url = reverse('common:company-detail', kwargs={'code': company.code})
        response = client.get(url)
        assert response.status_code == 200
        assert company.name in response.content.decode()
        assert company.express_database_name in response.content.decode()

    def test_company_create_view(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('common:company-create')
        data = {
            'name': 'New Company',
            'code': 'NEW01',
            'express_database_name': 'NEWDB',
            'status': 'active'
        }
        response = client.post(url, data)
        assert response.status_code == 302  # Redirection after success
        assert Company.objects.filter(code='NEW01').exists()

    def test_company_update_view(self, client, admin_user, company):
        client.force_login(admin_user)
        url = reverse('common:company-update', kwargs={'code': company.code})
        data = {
            'name': 'Updated Name',
            'code': company.code,
            'express_database_name': 'UPDATED_DB',
            'status': company.status
        }
        response = client.post(url, data)
        assert response.status_code == 302
        company.refresh_from_db()
        assert company.name == 'Updated Name'
        assert company.express_database_name == 'UPDATED_DB'

    def test_company_soft_delete_and_trash(self, client, admin_user, company):
        client.force_login(admin_user)
        
        # 1. Soft delete via view
        delete_url = reverse('common:company-delete', kwargs={'code': company.code})
        response = client.post(delete_url)
        assert response.status_code == 302
        
        company.refresh_from_db()
        assert company.is_deleted is True
        
        # 2. Verify in Trash list
        trash_url = reverse('common:company-trash')
        response = client.get(trash_url)
        assert response.status_code == 200
        assert company.name in response.content.decode()

    def test_company_restore(self, client, admin_user, company):
        client.force_login(admin_user)
        company.is_deleted = True
        company.save()
        
        restore_url = reverse('common:company-restore', kwargs={'code': company.code})
        response = client.post(restore_url)
        assert response.status_code == 302
        
        company.refresh_from_db()
        assert company.is_deleted is False

    def test_company_delete_blocked_by_active_warehouse(self, client, admin_user, company):
        client.force_login(admin_user)
        # Create active warehouse linked to company
        Warehouse.objects.create(
            code="TG001",
            name="Bangkok Warehouse",
            company=company,
            created_by=admin_user
        )
        delete_url = reverse('common:company-delete', kwargs={'code': company.code})
        response = client.post(delete_url)
        # Should stay on page or redirect to delete page and display error
        assert response.status_code == 200
        # Company should still be active
        company.refresh_from_db()
        assert company.is_deleted is False
