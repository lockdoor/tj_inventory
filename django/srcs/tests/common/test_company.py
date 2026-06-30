import pytest
from django.contrib.auth.models import User
from common.models import Company
from inventory.models import Warehouse
from inventory.services.express_service import ExpressService

@pytest.fixture
def user(db):
    return User.objects.create_user(username="test_admin", password="password123")

@pytest.mark.django_db
class TestCompanyModel:
    def test_company_creation_and_normalization(self, user):
        company = Company.objects.create(
            code="  tj69  ",
            name="  Thai Jintan 69  ",
            express_database_name="TJ69",
            created_by=user
        )
        assert company.code == "TJ69"
        assert company.name == "Thai Jintan 69"
        assert str(company) == "TJ69 - Thai Jintan 69"

    def test_warehouse_relationship(self, user):
        company = Company.objects.create(
            code="TJ69",
            name="Thai Jintan 69",
            express_database_name="TJ69",
            created_by=user
        )
        warehouse = Warehouse.objects.create(
            code="TG001",
            name="Bangkok Warehouse",
            company=company,
            created_by=user
        )
        assert warehouse.company == company
        assert company.warehouses.first() == warehouse

    def test_soft_delete_prevented_by_active_warehouses(self, user):
        from django.core.exceptions import ValidationError
        from common.services.company_service import CompanyService
        company = Company.objects.create(
            code="TJ69",
            name="Thai Jintan 69",
            express_database_name="TJ69",
            created_by=user
        )
        warehouse = Warehouse.objects.create(
            code="TG001",
            name="Bangkok Warehouse",
            company=company,
            created_by=user
        )
        with pytest.raises(ValidationError, match="Cannot delete company because it is referenced by active warehouses."):
            CompanyService.soft_delete(company, user=user)

        # But if the warehouse is soft-deleted, we should be able to delete the company!
        warehouse.delete(user=user)
        CompanyService.soft_delete(company, user=user)
        assert company.is_deleted is True


@pytest.mark.django_db
class TestExpressServiceMultiCompany:
    def test_get_companies_from_database(self, user):
        Company.objects.all().delete()
        Company.objects.create(
            code="TJ",
            name="Thai Jintan",
            express_database_name="TJ_DB",
            created_by=user
        )
        companies = ExpressService.get_companies()
        assert "TJ_DB" in companies

    def test_get_comparison_data_not_found(self):
        Company.objects.all().delete()
        with pytest.raises(Exception, match="Company 'UNKNOWN' not found"):
            ExpressService.get_comparison_data("UNKNOWN")

    def test_get_comparison_data_from_database(self, user):
        Company.objects.all().delete()
        company = Company.objects.create(
            code="TJ",
            name="Thai Jintan",
            express_database_name="TJ_DB",
            created_by=user
        )
        warehouse = Warehouse.objects.create(
            code="TJ_WH",
            name="TJ Warehouse",
            company=company,
            created_by=user
        )
        # Should execute successfully without throwing "not found" exception
        # since it resolves from the database
        data = ExpressService.get_comparison_data("TJ_DB")
        assert isinstance(data, list)
