import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from decimal import Decimal
from common.models import Company
from petty_cash.models import PettyCashAccount

@pytest.fixture
def manager_user(db):
    user = User.objects.create_user("manager", "manager@test.com", "pass")
    # Grant all petty cash account permissions
    content_type = ContentType.objects.get_for_model(PettyCashAccount)
    permissions = Permission.objects.filter(content_type=content_type)
    user.user_permissions.add(*permissions)
    return user

@pytest.fixture
def custodian_user(db):
    return User.objects.create_user("custodian", "custodian@test.com", "pass")

@pytest.fixture
def company(db, manager_user):
    return Company.objects.create(
        code="TJ",
        name="TJ Company",
        created_by=manager_user
    )

@pytest.fixture
def account(db, company, custodian_user, manager_user):
    return PettyCashAccount.objects.create(
        code="PC-HO-01",
        name="Head Office Box",
        company=company,
        custodian=custodian_user,
        balance=Decimal("1000.00"),
        max_limit=Decimal("5000.00"),
        created_by=manager_user
    )

@pytest.mark.django_db
class TestPettyCashAccountViews:

    def test_unauthenticated_redirect(self, client):
        response = client.get(reverse('petty_cash:account-list'))
        assert response.status_code == 302

    def test_list_view_and_search(self, client, manager_user, account):
        client.force_login(manager_user)
        response = client.get(reverse('petty_cash:account-list'))
        assert response.status_code == 200
        assert len(response.context['accounts']) == 1

        # Search match
        response = client.get(reverse('petty_cash:account-list'), {'q': 'HO-01'})
        assert len(response.context['accounts']) == 1

        # Search mismatch
        response = client.get(reverse('petty_cash:account-list'), {'q': 'NonExistent'})
        assert len(response.context['accounts']) == 0

    def test_detail_view(self, client, manager_user, account):
        client.force_login(manager_user)
        response = client.get(reverse('petty_cash:account-detail', kwargs={'pk': account.pk}))
        assert response.status_code == 200
        assert response.context['account'] == account

    def test_create_view_post_success(self, client, manager_user, company, custodian_user):
        client.force_login(manager_user)
        url = reverse('petty_cash:account-create')
        data = {
            'code': 'PC-HQ-02',
            'name': 'HQ Sub-Box',
            'company': company.pk,
            'custodian': custodian_user.pk,
            'balance': '2000.00',
            'max_limit': '5000.00',
            'currency': 'THB',
            'status': 'active',
            'note': 'Second box'
        }
        response = client.post(url, data)
        assert response.status_code == 302
        assert PettyCashAccount.objects.filter(code='PC-HQ-02').exists()

    def test_update_view_fields_locked(self, client, manager_user, account, custodian_user):
        client.force_login(manager_user)
        url = reverse('petty_cash:account-update', kwargs={'pk': account.pk})
        
        # Try sending a POST changing custodian, company and balance (which are disabled on the form)
        other_user = User.objects.create_user("other", "other@test.com", "pass")
        data = {
            'code': 'PC-HO-UPD',
            'name': 'Updated Name',
            'company': account.company.pk,
            # Even if form submits changed fields, the clean/save disables changes
            'custodian': other_user.pk,
            'balance': '9999.00', 
            'max_limit': '8000.00',
            'currency': 'THB',
            'status': 'inactive',
            'note': 'Updated notes'
        }
        response = client.post(url, data)
        assert response.status_code == 302
        
        # Re-fetch from DB and verify name/max_limit/status updated, but custodian & balance locked
        account.refresh_from_db()
        assert account.code == 'PC-HO-UPD'
        assert account.name == 'Updated Name'
        assert account.max_limit == Decimal('8000.00')
        assert account.status == 'inactive'
        assert account.custodian == custodian_user  # Remains unchanged!
        assert account.balance == Decimal('1000.00')  # Remains unchanged!

    def test_delete_trash_restore_lifecycle(self, client, manager_user, account):
        client.force_login(manager_user)
        
        # 1. Soft delete
        delete_url = reverse('petty_cash:account-delete', kwargs={'pk': account.pk})
        response = client.post(delete_url)
        assert response.status_code == 302
        
        account.refresh_from_db()
        assert account.is_deleted is True

        # 2. View Trash
        trash_url = reverse('petty_cash:account-trash')
        response = client.get(trash_url)
        assert response.status_code == 200
        assert account in response.context['accounts']

        # 3. Restore
        restore_url = reverse('petty_cash:account-restore', kwargs={'pk': account.pk})
        response = client.post(restore_url)
        assert response.status_code == 302
        
        account.refresh_from_db()
        assert account.is_deleted is False
