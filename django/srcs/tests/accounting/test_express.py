import pytest
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from common.models import Company
from accounting.models import PettyCashCategory
from accounting.services.express_service import ExpressService


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("admin", "admin@test.com", "pass")


@pytest.fixture
def company(db, admin_user):
    return Company.objects.create(
        code="TJ",
        name="TJ Company",
        express_database_name="TJ_DB",
        created_by=admin_user
    )


@pytest.mark.django_db
class TestPettyCashExpressService:

    @patch('requests.get')
    @patch('common.services.express_service.ExpressHelperService.get_companies')
    @patch('common.services.express_service.ExpressHelperService.get_express_location')
    def test_update_category_from_express_success(self, mock_get_loc, mock_get_companies, mock_get, company, admin_user):
        mock_get_loc.return_value = "http://localhost:8001/api/v1"
        mock_get_companies.return_value = ["TJ_DB"]

        # Mock response from FastAPI Express bridge
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = [
            {'ACCNUM': '5101-01', 'ACCNAM': 'Travel'},
            {'ACCNUM': '5102-02', 'ACCNAM': 'Supplies'}
        ]
        mock_get.return_value = mock_resp

        result = ExpressService.update_category_from_express(company, admin_user)
        assert len(result) == 2

        # Check records created
        assert PettyCashCategory.objects.filter(company=company, code="5101-01", name="Travel").exists()
        assert PettyCashCategory.objects.filter(company=company, code="5102-02", name="Supplies").exists()

        # Try updating name in subsequent sync
        mock_resp.json.return_value = [
            {'ACCNUM': '5101-01', 'ACCNAM': 'Travel Expenses'},
            {'ACCNUM': '5102-02', 'ACCNAM': 'Office Supplies'}
        ]
        result2 = ExpressService.update_category_from_express(company, admin_user)
        assert len(result2) == 2
        assert PettyCashCategory.objects.get(code="5101-01").name == "Travel Expenses"
        assert PettyCashCategory.objects.get(code="5102-02").name == "Office Supplies"
