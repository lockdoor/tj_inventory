import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Permission
from common.models import Company
from accounting.models import PettyCashCategory


@pytest.fixture
def user(db):
    return User.objects.create_user(username="testuser", password="password")


@pytest.fixture
def user_with_perms(db):
    u = User.objects.create_user(username="authuser", password="password")
    # Grant all petty cash category permissions
    perms = Permission.objects.filter(codename__endswith="pettycashcategory")
    u.user_permissions.add(*perms)
    return u


@pytest.fixture
def company(db, user_with_perms):
    return Company.objects.create(
        code="TJ",
        name="TJ Company",
        created_by=user_with_perms
    )


@pytest.fixture
def category(db, company, user_with_perms):
    return PettyCashCategory.objects.create(
        code="5101-01",
        name="Travel",
        company=company,
        created_by=user_with_perms
    )


@pytest.mark.django_db
class TestPettyCashViews:

    def test_overview_view_permissions(self, client, user, user_with_perms):
        # 1. Unauthenticated denied (redirect to login)
        response = client.get(reverse('accounting:overview'))
        assert response.status_code == 302

        # 2. Authenticated but unauthorized (403)
        client.force_login(user)
        response = client.get(reverse('accounting:overview'))
        assert response.status_code == 403

        # 3. Authorized (200)
        client.force_login(user_with_perms)
        response = client.get(reverse('accounting:overview'))
        assert response.status_code == 200
        assert 'modules' in response.context
    def test_category_list_view_and_search(self, client, user_with_perms, category):
        client.force_login(user_with_perms)
        
        # 1. View listing without company_id (shows company cards)
        response = client.get(reverse('accounting:category-list'))
        assert response.status_code == 200
        assert len(response.context['companies']) == 1
        assert len(response.context['categories']) == 0

        # 2. View listing with company_id
        response = client.get(reverse('accounting:category-list'), {'company_id': category.company.pk})
        assert response.status_code == 200
        assert len(response.context['categories']) == 1

        # 3. Search match
        response = client.get(reverse('accounting:category-list'), {'company_id': category.company.pk, 'q': 'Travel'})
        assert len(response.context['categories']) == 1

        # 4. Search mismatch
        response = client.get(reverse('accounting:category-list'), {'company_id': category.company.pk, 'q': 'NonExistent'})
        assert len(response.context['categories']) == 0

    def test_category_detail_view(self, client, user_with_perms, category):
        client.force_login(user_with_perms)
        response = client.get(reverse('accounting:category-detail', kwargs={'pk': category.pk}))
        assert response.status_code == 200
        assert response.context['category'] == category

    def test_category_create_view(self, client, user_with_perms, company):
        client.force_login(user_with_perms)
        
        # GET create form
        response = client.get(reverse('accounting:category-create'))
        assert response.status_code == 200

        # POST valid creation
        data = {
            'code': '5102-02',
            'name': 'Supplies',
            'company': company.pk,
            'note': 'Supplies description'
        }
        response = client.post(reverse('accounting:category-create'), data)
        # Should redirect to list
        assert response.status_code == 302
        assert PettyCashCategory.objects.filter(code="5102-02", is_deleted=False).exists()

        # POST duplicate code on same company raises validation error
        response = client.post(reverse('accounting:category-create'), data)
        assert response.status_code == 200  # Stays on form
        assert not response.context['form'].is_valid()

    def test_category_update_view(self, client, user_with_perms, category):
        client.force_login(user_with_perms)

        # GET update form
        response = client.get(reverse('accounting:category-update', kwargs={'pk': category.pk}))
        assert response.status_code == 200

        # POST update fields
        data = {
            'code': '5101-01',  # Keeps same code
            'name': 'Updated Travel Expenses',
            'company': category.company.pk,
            'note': 'Updated notes'
        }
        response = client.post(reverse('accounting:category-update', kwargs={'pk': category.pk}), data)
        assert response.status_code == 302
        
        category.refresh_from_db()
        assert category.name == "Updated Travel Expenses"
        assert category.note == "Updated notes"

    def test_category_delete_trash_restore_lifecycle(self, client, user_with_perms, category):
        client.force_login(user_with_perms)

        # 1. Soft-delete category
        response = client.post(reverse('accounting:category-delete', kwargs={'pk': category.pk}))
        assert response.status_code == 302
        
        category.refresh_from_db()
        assert category.is_deleted is True

        # 2. Check in trash list
        response = client.get(reverse('accounting:category-trash'))
        assert response.status_code == 200
        assert category in response.context['categories']

        # 3. Restore category
        response = client.post(reverse('accounting:category-restore', kwargs={'pk': category.pk}))
        assert response.status_code == 302

        category.refresh_from_db()
        assert category.is_deleted is False
