from django.shortcuts import redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from ..models import SalesOrder, SalesOrderAttachment
from ..forms.attachment_forms import SalesOrderAttachmentForm


class SalesOrderAttachmentUploadView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view to upload a single attachment for a specific Sales Order.
    """
    permission_required = 'sales.change_salesorder'
    
    def post(self, request, pk):
        order = get_object_or_404(SalesOrder, pk=pk)
        form = SalesOrderAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            attachment = form.save(commit=False)
            attachment.sales_order = order
            attachment.created_by = request.user
            attachment.updated_by = request.user
            attachment.save()
            messages.success(request, f"File '{attachment.file_name}' attached to SO {order.document_no}.")
        else:
            messages.error(request, "Failed to attach file. Please check the file format and size.")
            
        return redirect('sales:sales-order-detail', pk=order.pk)


class SalesOrderAttachmentDeleteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """
    POST view to delete a specific SO attachment.
    """
    permission_required = 'sales.change_salesorder'
    
    def post(self, request, pk):
        attachment = get_object_or_404(SalesOrderAttachment, pk=pk)
        order_pk = attachment.sales_order.pk
        file_name = attachment.file_name
        
        attachment.delete(user=request.user)
        messages.info(request, f"Attachment '{file_name}' removed from SO.")
        
        return redirect('sales:sales-order-detail', pk=order_pk)
