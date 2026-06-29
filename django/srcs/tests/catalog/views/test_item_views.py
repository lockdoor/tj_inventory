import pytest
from django.urls import reverse
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from catalog.models import Item, Category

@pytest.fixture(autouse=True)
def seed_groups(db):
    call_command('seed_groups')

@pytest.fixture
def executive_user(db):
    user = User.objects.create_user(username='executive', password='password123')
    if not Group.objects.filter(name='executive').exists():
        call_command('seed_groups')
    user.groups.add(Group.objects.get(name='executive'))
    return user

@pytest.fixture
def sales_user(db):
    user = User.objects.create_user(username='sales', password='password123')
    if not Group.objects.filter(name='sales_rep').exists():
        call_command('seed_groups')
    user.groups.add(Group.objects.get(name='sales_rep'))
    return user

@pytest.mark.django_db
class TestItemListView:
    """Functional tests for the Item List view."""

    def test_unauthenticated_denied(self, client):
        url = reverse('catalog:item-list')
        response = client.get(url)
        assert response.status_code == 403

    def test_sales_rep_authorized(self, client, sales_user):
        # Sales reps have 'view_item' permission
        client.login(username='sales', password='password123')
        url = reverse('catalog:item-list')
        response = client.get(url)
        assert response.status_code == 200

    def test_get_item_list_visibility(self, client, executive_user):
        cat = Category.objects.create(name='Test Cat', code='TC', created_by=executive_user)
        Item.objects.create(sku='ITEM1', name='Visible Item', unit='Pcs', category=cat, created_by=executive_user)
        Item.objects.create(sku='ITEM2', name='Hidden Item', unit='Pcs', category=cat, is_deleted=True, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-list')
        response = client.get(url)
        
        assert response.status_code == 200
        items = response.context['items']
        assert len(items) == 1
        assert items[0].sku == 'ITEM1'
        
        content = response.content.decode()
        assert 'Visible Item' in content
        assert 'Hidden Item' not in content
        assert 'Test Cat' in content

@pytest.mark.django_db
class TestItemCreateView:
    """Functional tests for Item creation."""

    def test_unauthenticated_denied(self, client):
        url = reverse('catalog:item-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_sales_rep_denied(self, client, sales_user):
        # Sales reps can view but not add
        client.login(username='sales', password='password123')
        url = reverse('catalog:item-create')
        response = client.get(url)
        assert response.status_code == 403

    def test_create_success(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        client.login(username='executive', password='password123')
        
        url = reverse('catalog:item-create')
        data = {
            'sku': 'NEW-SKU',
            'name': 'New Product',
            'category': cat.id,
            'unit': 'Pcs',
            'express_sku': 'EXP-123',
            'note': 'Fresh stock',
            'status': 'active'
        }
        
        response = client.post(url, data)
        assert response.status_code == 302
        assert response.url == reverse('catalog:item-list')
        
        # Verify in DB
        del_item = Item.objects.get(sku='NEW-SKU')
        assert del_item.name == 'New Product'
        assert del_item.created_by == executive_user

    def test_duplicate_sku_error(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        Item.objects.create(sku='DUP-01', name='Existing', unit='Pcs', category=cat, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-create')
        data = {
            'sku': 'DUP-01',
            'name': 'Should Fail',
            'category': cat.id,
            'unit': 'Pcs'
        }
        
        response = client.post(url, data)
        assert response.status_code == 200
        assert 'Item with this Sku already exists' in response.content.decode()

    def test_create_with_image_success(self, client, executive_user):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io
        
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        client.login(username='executive', password='password123')
        
        # Create a dummy non-square image
        image_content = io.BytesIO()
        img = Image.new('RGB', (800, 600), color='red')
        img.save(image_content, format='JPEG')
        image_content.seek(0)
        
        uploaded_image = SimpleUploadedFile(
            "test_photo.jpg", 
            image_content.read(), 
            content_type="image/jpeg"
        )
        
        url = reverse('catalog:item-create')
        data = {
            'sku': 'IMG-SKU',
            'name': 'Photo Product',
            'category': cat.id,
            'unit': 'Pcs',
            'status': 'active',
            'image': uploaded_image
        }
        
        response = client.post(url, data)
        assert response.status_code == 302
        
        # Verify in DB
        item = Item.objects.get(sku='IMG-SKU')
        assert item.images.count() == 1
        main_img = item.images.first()
        assert main_img.is_main
        
        # Verify naming (SKU in filename)
        assert 'IMG-SKU' in main_img.image.name
        assert main_img.image.name.endswith('.jpg')
        
        # Verify processing (check size if pillow is available to read)
        saved_img = Image.open(main_img.image.path)
        assert saved_img.size == (800, 600)  # Should remain original size (800, 600)

@pytest.mark.django_db
class TestItemUpdateView:
    """Functional tests for Item updates."""

    def test_update_success(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        item = Item.objects.create(sku='SKU-1', name='Old Name', unit='Pcs', category=cat, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-update', kwargs={'sku': item.sku})
        
        # Verify title in GET request before update
        response = client.get(url)
        assert f"Update {item.name}" in response.content.decode()

        data = {
            'sku': 'SKU-1',  # Keep same SKU
            'name': 'Updated Name',
            'category': cat.id,
            'unit': 'Kg',
            'note': 'Price drop',
            'express_sku': '',
            'status': 'active'
        }
        
        response = client.post(url, data)
        assert response.status_code == 302
        assert response.url == reverse('catalog:item-detail', kwargs={'sku': item.sku})
        
        item.refresh_from_db()
        assert item.name == 'Updated Name'
        assert item.unit == 'Kg'
        assert item.updated_by == executive_user

    def test_update_status_toggle(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        item = Item.objects.create(sku='SKU-T', name='Toggle Test', unit='Pcs', category=cat, created_by=executive_user)
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-update', kwargs={'sku': item.sku})
        
        # Deactivate
        data = {
            'sku': 'SKU-T',
            'name': 'Toggle Test',
            'category': cat.id,            
            'unit': 'Pcs',
            'status': 'inactive'
        }
        response = client.post(url, data)
        assert response.status_code == 302
        
        item.refresh_from_db()
        assert item.status == 'inactive'
        
        # Reactivate
        data['status'] = 'active'
        response = client.post(url, data)
        assert response.status_code == 302
        
        item.refresh_from_db()
        assert item.status == 'active'

@pytest.mark.django_db
class TestItemDetailView:
    """Functional tests for the Item Detail view."""

    def test_unauthenticated_denied(self, client, executive_user):
        item = Item.objects.create(sku='SKU-1', name='Item', unit='Pcs', created_by=executive_user)
        url = reverse('catalog:item-detail', kwargs={'sku': item.sku})
        response = client.get(url)
        assert response.status_code == 403

    def test_sales_rep_authorized(self, client, sales_user, executive_user):
        item = Item.objects.create(sku='SKU-1', name='Item', unit='Pcs', created_by=executive_user)
        client.login(username='sales', password='password123')
        url = reverse('catalog:item-detail', kwargs={'sku': item.sku})
        response = client.get(url)
        assert response.status_code == 200
        assert item.name in response.content.decode()

    def test_detail_content_and_links(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        item = Item.objects.create(
            sku='SKU-DETAIL', 
            name='Detail Item', 
            unit='Boxes', 
            category=cat, 
            express_sku='EXP-DET',
            note='Detailed notes here',
            created_by=executive_user
        )
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-detail', kwargs={'sku': item.sku})
        response = client.get(url)
        
        assert response.status_code == 200
        content = response.content.decode()
        
        # Verify fields
        assert 'SKU-DETAIL' in content
        assert 'Detail Item' in content
        assert 'Electronics' in content
        assert 'Boxes' in content
        assert 'EXP-DET' in content
        assert 'Detailed notes here' in content
        
        # Verify audit info
        assert executive_user.username in content
        
        # Verify update link
        update_url = reverse('catalog:item-update', kwargs={'sku': item.sku})
        assert update_url in content
        
        # Verify delete link
        delete_url = reverse('catalog:item-delete', kwargs={'sku': item.sku})
        assert delete_url in content

@pytest.mark.django_db
class TestItemTrashView:
    """Functional tests for Item Trash and Restore."""

    def test_unauthenticated_denied(self, client, executive_user):
        url = reverse('catalog:item-trash')
        response = client.get(url)
        assert response.status_code == 403

    def test_sales_rep_denied(self, client, sales_user):
        client.login(username='sales', password='password123')
        url = reverse('catalog:item-trash')
        response = client.get(url)
        assert response.status_code == 403

    def test_trash_visibility_and_restore(self, client, executive_user):
        cat = Category.objects.create(name='Electronics', code='ELEC', created_by=executive_user)
        item = Item.objects.create(sku='DEL-SKU', name='Deleted Product', unit='Pcs', category=cat, is_deleted=True, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        
        # Check Trash List
        url_trash = reverse('catalog:item-trash')
        response = client.get(url_trash)
        assert response.status_code == 200
        assert 'DEL-SKU' in response.content.decode()
        assert 'Deleted Product' in response.content.decode()

        # Perform Restore
        url_restore = reverse('catalog:item-restore', kwargs={'sku': item.sku})
        response = client.post(url_restore)
        assert response.status_code == 302
        assert response.url == reverse('catalog:item-list')

        # Verify restored in DB
        item.refresh_from_db()
        assert not item.is_deleted
        assert item.deleted_at is None
        assert item.updated_by == executive_user

@pytest.mark.django_db
class TestItemDeleteView:
    """Functional tests for Item Delete view."""

    def test_unauthenticated_denied(self, client, executive_user):
        item = Item.objects.create(sku='T1', name='Test', unit='Pcs', created_by=executive_user)
        url = reverse('catalog:item-delete', kwargs={'sku': item.sku})
        response = client.get(url)
        assert response.status_code == 403

    def test_executive_delete_success(self, client, executive_user):
        cat = Category.objects.create(name='Cat', code='C', created_by=executive_user)
        item = Item.objects.create(sku='TO-DEL', name='To Delete', unit='Pcs', category=cat, created_by=executive_user)
        
        client.login(username='executive', password='password123')
        url = reverse('catalog:item-delete', kwargs={'sku': item.sku})
        
        # GET show confirmation
        response = client.get(url)
        assert response.status_code == 200
        assert 'Delete Item?' in response.content.decode()
        assert item.sku in response.content.decode()

        # POST confirm delete
        response = client.post(url)
        assert response.status_code == 302
        assert response.url == reverse('catalog:item-list')

        # Verify soft-deleted
        item.refresh_from_db()
        assert item.is_deleted
        assert item.deleted_by == executive_user
        assert item.deleted_at is not None
