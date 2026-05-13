from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from ..models import PurchaseOrder, PurchaseOrderAttachment, Arrival, ArrivalAttachment
from ..forms.attachment_forms import PurchaseOrderAttachmentForm, ArrivalAttachmentForm

class PurchaseOrderAttachmentUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view to upload a single attachment for a specific Purchase Order.
    """
    permission_required = 'procurement.change_purchaseorder'
    
    def post(self, request, pk):
        po = get_object_or_404(PurchaseOrder, pk=pk)
        form = PurchaseOrderAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.purchase_order = po
            attachment.created_by = request.user
            attachment.updated_by = request.user
            attachment.save()
            messages.success(request, f"File '{attachment.file_name}' attached to PO {po.document_no}.")
        else:
            messages.error(request, "Failed to attach file. Please check the file format and size.")
            
        return redirect('procurement:purchase-order-detail', pk=po.pk)

class PurchaseOrderAttachmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view to delete a specific PO attachment.
    """
    permission_required = 'procurement.change_purchaseorder'
    
    def post(self, request, pk):
        attachment = get_object_or_404(PurchaseOrderAttachment, pk=pk)
        po_pk = attachment.purchase_order.pk
        file_name = attachment.file_name
        
        attachment.delete(user=request.user)
        messages.info(request, f"Attachment '{file_name}' removed from PO.")
        
        return redirect('procurement:purchase-order-detail', pk=po_pk)

class ArrivalAttachmentUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view to upload a single attachment for a specific Arrival.
    """
    permission_required = 'procurement.change_arrival'
    
    def post(self, request, pk):
        arrival = get_object_or_404(Arrival, pk=pk)
        form = ArrivalAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.arrival = arrival
            attachment.created_by = request.user
            attachment.updated_by = request.user
            attachment.save()
            messages.success(request, f"File '{attachment.file_name}' attached to Arrival {arrival.document_no}.")
        else:
            messages.error(request, "Failed to attach file. Please check the file format and size.")
            
        return redirect('procurement:arrival-detail', pk=arrival.pk)

class ArrivalAttachmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view to delete a specific Arrival attachment.
    """
    permission_required = 'procurement.change_arrival'
    
    def post(self, request, pk):
        attachment = get_object_or_404(ArrivalAttachment, pk=pk)
        arrival_pk = attachment.arrival.pk
        file_name = attachment.file_name
        
        attachment.delete(user=request.user)
        messages.info(request, f"Attachment '{file_name}' removed from Arrival.")
        
        return redirect('procurement:arrival-detail', pk=arrival_pk)
