import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from common.models import Individual


@pytest.fixture
def user(db):
    return User.objects.create_user("john_doe", "john@test.com", "pass")


@pytest.mark.django_db
class TestIndividualModel:
    """
    Tests verifying validation, normalizations, and relationship constraints 
    on the Individual model with bilingual name support.
    """

    def test_individual_creation_and_normalizations(self, user):
        ind = Individual.objects.create(
            first_name_th="  สมชาย  ",
            last_name_th="  ดีใจ  ",
            first_name_en="  Somchai  ",
            last_name_en="  Deejai  ",
            nickname="  สม  ",
            email="  SOMCHAI@test.com  ",
            phones=["+6621234567", "+66898765432"],
            created_by=user
        )
        
        # Verify names are trimmed
        assert ind.first_name_th == "สมชาย"
        assert ind.last_name_th == "ดีใจ"
        assert ind.first_name_en == "Somchai"
        assert ind.last_name_en == "Deejai"
        assert ind.nickname == "สม"
        
        # Verify email is trimmed and converted to lowercase
        assert ind.email == "somchai@test.com"
        
        # Verify string conversion includes nickname
        assert str(ind) == "สมชาย ดีใจ (สม)"
        assert ind.full_name == "สมชาย ดีใจ (สม)"
        
        # Verify phones JSONField lists are stored correctly
        assert isinstance(ind.phones, list)
        assert len(ind.phones) == 2
        assert ind.phones[0] == "+6621234567"

    def test_optional_user_relationship(self, user):
        # Create an individual with no linked User
        ind_no_user = Individual.objects.create(
            first_name_th="สมหญิง",
            last_name_th="สุขใจ",
            created_by=user
        )
        assert ind_no_user.user is None

        # Create an individual linked to a User
        ind_with_user = Individual.objects.create(
            first_name_th="สมหมาย",
            last_name_th="รักดี",
            user=user,
            created_by=user
        )
        assert ind_with_user.user == user
        assert user.individual == ind_with_user

    def test_phones_normalization_to_list(self, user):
        ind = Individual.objects.create(
            first_name_th="สมพงษ์",
            last_name_th="มาดี",
            phones="not a list",
            created_by=user
        )
        assert ind.phones == []
