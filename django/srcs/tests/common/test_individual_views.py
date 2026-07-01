import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from common.models import Individual


@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser("admin", "admin@test.com", "pass")
    perms = Permission.objects.filter(codename__endswith='_individual')
    user.user_permissions.add(*perms)
    return user


@pytest.fixture
def individual(db, admin_user):
    return Individual.objects.create(
        first_name_th="ทดสอบ", 
        last_name_th="ระบบ", 
        first_name_en="Test", 
        last_name_en="System", 
        nickname="บอท", 
        email="test@test.com",
        phones=["+66812345678"],
        created_by=admin_user
    )


@pytest.fixture
def unauthorized_user(db):
    """User with no permissions."""
    return User.objects.create_user("plain_user", "plain@test.com", "pass")


@pytest.mark.django_db
class TestIndividualPermissions:
    """Security tests verifying that unauthorized users are denied access (403)."""

    def test_list_denied(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('common:individual-list')
        response = client.get(url)
        assert response.status_code == 403

    def test_create_denied(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('common:individual-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_update_denied(self, client, unauthorized_user, individual):
        client.force_login(unauthorized_user)
        url = reverse('common:individual-update', kwargs={'pk': individual.pk})
        response = client.get(url)
        assert response.status_code == 403

    def test_delete_denied(self, client, unauthorized_user, individual):
        client.force_login(unauthorized_user)
        url = reverse('common:individual-delete', kwargs={'pk': individual.pk})
        response = client.post(url)
        assert response.status_code == 403

    def test_trash_denied(self, client, unauthorized_user):
        client.force_login(unauthorized_user)
        url = reverse('common:individual-trash')
        response = client.get(url)
        assert response.status_code == 403

    def test_restore_denied(self, client, unauthorized_user, individual):
        client.force_login(unauthorized_user)
        individual.is_deleted = True
        individual.save()
        
        url = reverse('common:individual-restore', kwargs={'pk': individual.pk})
        response = client.post(url)
        assert response.status_code == 403


@pytest.mark.django_db
class TestIndividualCRUD:
    """Functional tests for Individual Create, Update, Detail, Delete, and Restore."""

    def test_individual_list_view(self, client, admin_user, individual):
        client.force_login(admin_user)
        url = reverse('common:individual-list')
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert individual.first_name_th in content
        assert f"({individual.nickname})" in content

    def test_individual_detail_view(self, client, admin_user, individual):
        client.force_login(admin_user)
        url = reverse('common:individual-detail', kwargs={'pk': individual.pk})
        response = client.get(url)
        assert response.status_code == 200
        content = response.content.decode()
        assert individual.first_name_th in content
        assert individual.first_name_en in content
        assert individual.nickname in content
        assert individual.email in content

    def test_individual_create_view(self, client, admin_user):
        client.force_login(admin_user)
        url = reverse('common:individual-create')
        data = {
            'first_name_th': 'สมชาย',
            'last_name_th': 'ดีใจ',
            'first_name_en': 'Somchai',
            'last_name_en': 'Deejai',
            'nickname': 'สม',
            'email': 'new@test.com',
            'phones': '+66898765432, +6621234567'
        }
        response = client.post(url, data)
        assert response.status_code == 302
        new_ind = Individual.objects.get(email='new@test.com')
        assert new_ind.first_name_th == 'สมชาย'
        assert new_ind.nickname == 'สม'
        assert new_ind.phones == ['+66898765432', '+6621234567']

    def test_individual_update_view(self, client, admin_user, individual):
        client.force_login(admin_user)
        url = reverse('common:individual-update', kwargs={'pk': individual.pk})
        data = {
            'first_name_th': 'สมศรี',
            'last_name_th': individual.last_name_th,
            'first_name_en': 'Somsri',
            'last_name_en': individual.last_name_en,
            'nickname': 'ศรี',
            'email': 'updated@test.com',
            'phones': '+66888888888'
        }
        response = client.post(url, data)
        assert response.status_code == 302
        individual.refresh_from_db()
        assert individual.first_name_th == 'สมศรี'
        assert individual.nickname == 'ศรี'
        assert individual.email == 'updated@test.com'
        assert individual.phones == ['+66888888888']

    def test_individual_soft_delete_and_trash(self, client, admin_user, individual):
        client.force_login(admin_user)
        
        # 1. Soft delete
        delete_url = reverse('common:individual-delete', kwargs={'pk': individual.pk})
        response = client.post(delete_url)
        assert response.status_code == 302
        
        individual.refresh_from_db()
        assert individual.is_deleted is True
        
        # 2. Trash list assertion
        trash_url = reverse('common:individual-trash')
        response = client.get(trash_url)
        assert response.status_code == 200
        assert individual.first_name_th in response.content.decode()

    def test_individual_restore(self, client, admin_user, individual):
        client.force_login(admin_user)
        individual.is_deleted = True
        individual.save()
        
        restore_url = reverse('common:individual-restore', kwargs={'pk': individual.pk})
        response = client.post(restore_url)
        assert response.status_code == 302
        
        individual.refresh_from_db()
        assert individual.is_deleted is False
