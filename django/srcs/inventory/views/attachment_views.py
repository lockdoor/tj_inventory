from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from inventory.models import InventoryMovement, InventoryMovementAttachment
from inventory.forms.attachment_form import MovementAttachmentForm

class MovementAttachmentUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view to upload a single attachment for a specific movement.
    Accessible from the Movement Detail page.
    """
    permission_required = 'inventory.change_inventorymovement'
    
    def post(self, request, pk):
        movement = get_object_or_404(InventoryMovement, pk=pk)
        
        # Only allow attachments on documents that aren't hard-deleted
        # (Soft-deleted is okay if the user is in the trash view, but usually not)
        
        form = MovementAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.movement = movement
            attachment.created_by = request.user
            attachment.updated_by = request.user
            attachment.save()
            messages.success(request, f"File '{attachment.file_name}' attached successfully.")
        else:
            messages.error(request, "Failed to attach file. Please check the file format and size.")
            
        return redirect('inventory:movement-detail', pk=movement.pk)

class MovementAttachmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view to delete a specific attachment.
    """
    permission_required = 'inventory.change_inventorymovement'
    
    def post(self, request, pk):
        attachment = get_object_or_404(InventoryMovementAttachment, pk=pk)
        movement_pk = attachment.movement.pk
        file_name = attachment.file_name
        
        attachment.delete(user=request.user)
        messages.info(request, f"Attachment '{file_name}' removed.")
        
        return redirect('inventory:movement-detail', pk=movement_pk)
