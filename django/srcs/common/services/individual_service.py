from django.core.exceptions import ValidationError
from common.models import Individual


class IndividualService:

    @staticmethod
    def get_active_queryset():
        """
        Return a base queryset of non-deleted individuals.
        """
        return Individual.objects.filter(is_deleted=False)

    @staticmethod
    def list_active():
        """
        Return all active (non-deleted) individuals ordered by first_name_th.
        """
        return IndividualService.get_active_queryset().order_by('first_name_th', 'last_name_th')

    @staticmethod
    def list_deleted():
        """
        Return all soft-deleted individuals ordered by first_name_th.
        """
        return Individual.objects.filter(is_deleted=True).order_by('first_name_th', 'last_name_th')

    @staticmethod
    def create(*, first_name_th, last_name_th, first_name_en='', last_name_en='', nickname='', user=None, email='', phones=None, created_by, **extra_fields):
        """
        Create a new individual.
        """
        if phones is None:
            phones = []
        
        individual = Individual(
            first_name_th=first_name_th,
            last_name_th=last_name_th,
            first_name_en=first_name_en,
            last_name_en=last_name_en,
            nickname=nickname,
            user=user,
            email=email,
            phones=phones,
            created_by=created_by,
            **extra_fields
        )
        individual.full_clean()
        individual.save()
        return individual

    @staticmethod
    def update(individual, *, updated_by, **fields):
        """
        Update an existing individual.
        """
        allowed_fields = {
            'first_name_th', 'last_name_th', 'first_name_en', 
            'last_name_en', 'nickname', 'user', 'email', 'phones'
        }
        for field, value in fields.items():
            if field in allowed_fields:
                setattr(individual, field, value)

        individual.updated_by = updated_by
        individual.full_clean()
        individual.save()
        return individual

    @staticmethod
    def soft_delete(individual, *, user):
        """
        Soft-delete an individual.
        """
        individual.delete(user=user)

    @staticmethod
    def restore(individual, *, user):
        """
        Restore a soft-deleted individual.
        """
        individual.restore(user=user)
        return individual
