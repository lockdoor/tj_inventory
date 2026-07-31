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
        category_count = PettyCashCategory.objects.filter(is_deleted=False).count()
        account_count = PettyCashAccount.objects.filter(is_deleted=False).count()
        
        context['page_title'] = "Accounting Overview"
        context['modules'] = [
            {
                'title': 'Expense Categories',
                'description': 'Map expense categories to GL accounting codes (ผังบัญชี) for each company.',
                'url': 'accounting:category-list',
                'icon_name': 'hash',
                'icon_class': 'category-icon',
                'badge': f"{category_count} Categories"
            },
            {
                'title': 'Petty Cash Accounts',
                'description': 'Configure petty cash boxes, maximum balances, limits, and custodians.',
                'url': 'accounting:account-list',
                'icon_name': 'wallet',
                'icon_class': 'pettycash-icon',
                'badge': f"{account_count} Accounts"
            }
        ]
        return context
