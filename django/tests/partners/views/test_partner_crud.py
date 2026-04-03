import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from partners.models import Partner

@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser("admin", "admin@test.com", "pass")
    # Grant all partner permissions
    perms = Permission.objects.filter(codename__endswith='_partner')
    user.user_permissions.add(*perms)
    return user

@pytest.fixture
def partner(db, admin_user):
    return Partner.objects.create(
        name="Test Partner", 
        code="TEST001", 
        is_supplier=True, 
        created_by=admin_user
    )

@pytest.fixture
def unauthorized_user(db):
    """User with no permissions."""
    return User.objects.create_user("plain_user", "plain@test.com", "pass")

@pytest.mark.django_db
class TestPartnerPermissions:
    """Security tests verifying that unauthorized users are denied access (403)."""

    def test_create_denied(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('partners:partner-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_update_denied(self, client, unauthorized_user, partner):
        client.force_login(unauthorized_user)
        url = reverse('partners:partner-update', kwargs={'code': partner.code})
        response = client.get(url)
        assert response.status_code == 403

    def test_delete_denied(self, client, unauthorized_user, partner):
        client.force_login(unauthorized_user)
        url = reverse('partners:partner-delete', kwargs={'code': partner.code})
        response = client.post(url)
        assert response.status_code == 403

    def test_trash_denied(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('partners:partner-trash')
        response = client.get(url)
        assert response.status_code == 403

    def test_restore_denied(self, client, unauthorized_user, partner):
        client.force_login(unauthorized_user)
        partner.is_deleted = True
        partner.save()
        
        url = reverse('partners:partner-restore', kwargs={'code': partner.code})
        response = client.post(url)
        assert response.status_code == 403

@pytest.mark.django_db
class TestPartnerCRUD:
    """Functional tests for Partner Create, Update, Detail, Delete, and Restore."""

    def test_partner_detail_view(self, client, admin_user, partner):
        client.force_login(admin_user)
        url = reverse('partners:partner-detail', kwargs={'code': partner.code})
        response = client.get(url)
        assert response.status_code == 200
        assert partner.name in response.content.decode()
        assert "Supplier" in response.content.decode()

    def test_partner_create_view(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('partners:partner-create')
        data = {
            'name': 'New Company',
            'code': 'NEW-01',
            'is_supplier': True,
            'is_customer': False,
            'status': 'active'
        }
        response = client.post(url, data)
        assert response.status_code == 302  # Redirection after success
        assert Partner.objects.filter(code='NEW-01').exists()

    def test_partner_update_view(self, client, admin_user, partner):
        client.force_login(admin_user)
        url = reverse('partners:partner-update', kwargs={'code': partner.code})
        data = {
            'name': 'Updated Name',
            'code': partner.code,
            'is_supplier': partner.is_supplier,
            'is_customer': True,  # Change role
            'status': partner.status
        }
        response = client.post(url, data)
        assert response.status_code == 302
        partner.refresh_from_db()
        assert partner.name == 'Updated Name'
        assert partner.is_customer is True

    def test_partner_soft_delete_and_trash(self, client, admin_user, partner):
        client.force_login(admin_user)
        
        # 1. Soft delete via view
        delete_url = reverse('partners:partner-delete', kwargs={'code': partner.code})
        response = client.post(delete_url)
        assert response.status_code == 302
        
        partner.refresh_from_db()
        assert partner.is_deleted is True
        
        # 2. Verify in Trash list
        trash_url = reverse('partners:partner-trash')
        response = client.get(trash_url)
        assert response.status_code == 200
        assert partner.name in response.content.decode()

    def test_partner_restore(self, client, admin_user, partner):
        client.force_login(admin_user)
        partner.is_deleted = True
        partner.save()
        
        restore_url = reverse('partners:partner-restore', kwargs={'code': partner.code})
        response = client.post(restore_url)
        assert response.status_code == 302
        
        partner.refresh_from_db()
        assert partner.is_deleted is False
