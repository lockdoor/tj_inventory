import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Group

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

@pytest.mark.django_db
def test_dashboard_sales_rep_access(client, test_user):
    """User in sales_rep group gets the sales dashboard."""
    sales_rep_group = Group.objects.create(name='sales_rep')
    test_user.groups.add(sales_rep_group)
    client.force_login(test_user)
    
    url = reverse('dashboard:home')
    response = client.get(url)
    assert response.status_code == 200
    
    # Check template
    assert 'dashboard/sales_dashboard.html' in [t.name for t in response.templates]
    
    # Check context
    assert response.context['page_title'] == "Sales Command Center"
    assert 'stats' in response.context
    assert 'confirmed_count' in response.context['stats']
    assert 'preorder_count' in response.context['stats']
    assert 'draft_count' in response.context['stats']
    assert 'total_revenue' in response.context['stats']
    
    # Modules check
    modules = response.context['modules']
    titles = [m['title'] for m in modules]
    assert 'Sales Orders' in titles
    assert 'Product Catalog' in titles
    assert 'Partner Database' in titles

@pytest.mark.django_db
def test_dashboard_stock_controller_access(client, test_user):
    """User in stock_controller group gets the stock controller dashboard."""
    group = Group.objects.create(name='stock_controller')
    test_user.groups.add(group)
    client.force_login(test_user)
    
    url = reverse('dashboard:home')
    response = client.get(url)
    assert response.status_code == 200
    assert 'dashboard/stock_controller_dashboard.html' in [t.name for t in response.templates]
    assert response.context['page_title'] == "Stock Controller Command Center"

@pytest.mark.django_db
def test_dashboard_warehouse_admin_access(client, test_user):
    """User in warehouse_admin group gets the warehouse admin dashboard."""
    group = Group.objects.create(name='warehouse_admin')
    test_user.groups.add(group)
    client.force_login(test_user)
    
    url = reverse('dashboard:home')
    response = client.get(url)
    assert response.status_code == 200
    assert 'dashboard/warehouse_dashboard.html' in [t.name for t in response.templates]
    assert response.context['page_title'] == "Warehouse Control Center"