from django.db.models.signals import post_save
from django.dispatch import receiver
from inventory.models import InventoryMovement
from .services.arrival_service import ArrivalService

@receiver(post_save, sender=InventoryMovement)
def handle_movement_update(sender, instance, created, **kwargs):
    """
    Listens for InventoryMovement updates to sync Arrival state.
    """
    if instance.reference_type == InventoryMovement.ReferenceType.STOCK_ARRIVAL:
        # Note: instance.updated_by should ideally be passed, 
        # but signals don't have request context.
        # We'll use the user who last updated the movement.
        user = instance.updated_by
        ArrivalService.finalize_from_movement(instance, user)
