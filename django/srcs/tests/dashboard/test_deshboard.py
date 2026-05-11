import pytest
from django.urls import reverse
from django.contrib.auth.models import User

@pytest.fixture
def test_user(db):
    return User.objects.create_user(username="testuser", password="password123")

@pytest.mark.django_db
def test_dashboard_login_required(client):
    """Unauthorized users should be redirected to login."""
    url = reverse('dashboard:home')
    response = client.get(url)
    assert response.status_code == 302
    assert "login" in response.url

@pytest.mark.django_db
def test_dashboard_access_for_logged_in_user(client, test_user):
    """Authenticated users should see the dashboard and links."""
    client.force_login(test_user)
    url = reverse('dashboard:home')
    response = client.get(url)
    assert response.status_code == 200
    content = response.content.decode()
    assert "Catalog Management" in content
    assert "Partner Database" in content
    assert reverse('catalog:catalog-overview') in content
    assert reverse('partners:partner-list') in content