from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sales'

    def ready(self):
        # Explicitly import sales_order models to register signal receivers
        import sales.models.sales_order
