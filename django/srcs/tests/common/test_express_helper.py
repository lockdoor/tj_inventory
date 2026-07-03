import pytest
from django.conf import settings
from common.models import Company
from common.services.express_service import ExpressHelperService


@pytest.mark.django_db
class TestExpressHelperService:
    def test_get_companies(self, admin_user):
        Company.objects.all().delete()
        Company.objects.create(
            code="TJ",
            name="Thai Jintan",
            express_database_name="TJ_DB",
            created_by=admin_user
        )
        companies = ExpressHelperService.get_companies()
        assert "TJ_DB" in companies

    def test_is_configured(self):
        configured = ExpressHelperService.is_configured()
        assert isinstance(configured, bool)

    def test_get_express_location(self):
        location = ExpressHelperService.get_express_location()
        assert location == getattr(settings, 'EXPRESS_LOCATION', None)
