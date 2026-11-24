from django.contrib import admin
from .models import PlanRun, Block


@admin.register(PlanRun)
class PlanRunAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'label',
        'created_at',
        'is_baseline',
        'is_whatif',
        'scheduled_count',
        'deferred_count',
        'conflicts',
        'total_traffic_impact',
        'availability_pct',
    )
    list_filter = ('is_baseline', 'is_whatif', 'horizon_days')
    search_fields = ('label',)
    readonly_fields = ('created_at',)


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'plan_run',
        'request',
        'section',
        'day',
        'start_hour',
        'end_hour',
        'cost',
    )
    list_filter = ('day', 'section', 'plan_run')
    search_fields = ('section__code', 'request__id')
