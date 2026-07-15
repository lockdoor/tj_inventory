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
    list_display = ('first_name_th', 'last_name_th', 'nickname', 'email', 'created_at')
    search_fields = ('first_name_th', 'last_name_th', 'nickname', 'first_name_en', 'last_name_en', 'email')
    raw_id_fields = ('user',)
