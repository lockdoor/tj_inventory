from django.contrib import admin
from common.models import Company

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'tax_id', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('code', 'name', 'tax_id')
    ordering = ('code',)
