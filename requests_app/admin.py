from django.contrib import admin
from .models import MaintenanceRequest


@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'asset', 'get_section_code', 'priority', 'duration_hours',
        'deadline_day', 'status', 'source', 'created_at',
    ]
    list_filter = ['status', 'source', 'priority', 'deadline_day']
    search_fields = ['description', 'asset__name', 'asset__section__code']
    list_per_page = 25
    ordering = ['-priority', 'deadline_day', 'created_at']

    @admin.display(description='Section', ordering='asset__section__code')
    def get_section_code(self, obj):
        return obj.asset.section.code
