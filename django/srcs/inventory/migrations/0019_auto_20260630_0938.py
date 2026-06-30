from django.db import migrations

def link_warehouses_to_companies(apps, schema_editor):
    Company = apps.get_model('common', 'Company')
    Warehouse = apps.get_model('inventory', 'Warehouse')
    User = apps.get_model('auth', 'User')
    
    system_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
    if not system_user:
        system_user = User.objects.create(
            username='system_migration',
            email='system@localhost',
            is_active=False
        )
    
    # Mapping of express_database_name -> warehouse_code
    company_warehouse_codes = {"TJ69": "TG001", "JINTAN68": "TJ001"}
    
    for express_db, wh_code in company_warehouse_codes.items():
        company_name = f"Company {express_db}"
        company_code = ''.join([c for c in express_db if c.isalpha()]).upper()
        if not company_code:
            company_code = express_db
            
        company, created = Company.objects.get_or_create(
            express_database_name=express_db,
            defaults={
                'code': company_code,
                'name': company_name,
                'status': 'active',
                'created_by': system_user,
            }
        )
        
        # Link the Warehouse to this Company
        warehouse = Warehouse.objects.filter(code=wh_code).first()
        if warehouse:
            warehouse.company = company
            warehouse.save()

def unlink_warehouses_from_companies(apps, schema_editor):
    Warehouse = apps.get_model('inventory', 'Warehouse')
    Warehouse.objects.update(company=None)


class Migration(migrations.Migration):

    dependencies = [
        ('common', '0002_company_historicalcompany'),
        ('inventory', '0018_historicalwarehouse_company_warehouse_company'),
    ]

    operations = [
        migrations.RunPython(link_warehouses_to_companies, unlink_warehouses_from_companies),
    ]
