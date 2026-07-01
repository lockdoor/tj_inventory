from django.contrib import admin
from common.models import Company, Individual

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'tax_id', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('code', 'name', 'tax_id')
    ordering = ('code',)

@admin.register(Individual)
class IndividualAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'email', 'created_at')
    search_fields = ('first_name', 'last_name', 'email')
    raw_id_fields = ('user',)
