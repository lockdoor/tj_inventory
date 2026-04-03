from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    The main landing page of the application after logging in.
    Provides entry points (cards) to authorized modules.
    """
    template_name = 'dashboard/overview.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Define module cards with icons and descriptions
        # In the future, this list can be dynamic based on user permissions/groups.
        modules = [
            {
                'title': 'Catalog Management',
                'description': 'Manage product categories, items, and audit history.',
                'url': 'catalog:catalog-overview',
                'icon_svg': '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>',
                'badge': 'Product Master'
            },
            {
                'title': 'Partner Database',
                'description': 'Track your global suppliers and customer network.',
                'url': 'partners:partner-list',
                'icon_svg': '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>',
                'badge': 'External Entities'
            },
        ]
        
        context['modules'] = modules
        context['page_title'] = "Executive Dashboard"
        return context
