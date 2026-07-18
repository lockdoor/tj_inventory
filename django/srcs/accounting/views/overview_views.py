from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from accounting.models import PettyCashCategory, PettyCashAccount, PettyCashPayment


class PettyCashOverviewView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """
    Overview page with cards to Category, Account, and Payment sub-modules.
    """
    template_name = 'accounting/overview.html'
    permission_required = 'accounting.view_pettycashcategory'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['category_count'] = PettyCashCategory.objects.filter(is_deleted=False).count()
        context['account_count'] = PettyCashAccount.objects.filter(is_deleted=False).count()
        context['payment_count'] = PettyCashPayment.objects.filter(is_deleted=False).count()
        return context
