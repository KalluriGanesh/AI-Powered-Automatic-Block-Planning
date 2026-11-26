from django.contrib import admin
from .models import Section, Asset, TrafficSlot, UserAccount


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'length_km', 'is_blocked', 'asset_count')
    list_filter = ('is_blocked',)
    search_fields = ('code', 'name')
    list_editable = ('is_blocked',)

    def asset_count(self, obj):
        return obj.assets.count()
    asset_count.short_description = 'Assets'


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = ('name', 'section', 'asset_type', 'health_score')
    list_filter = ('asset_type', 'section')
    search_fields = ('name', 'section__code', 'section__name')


@admin.register(TrafficSlot)
class TrafficSlotAdmin(admin.ModelAdmin):
    list_display = ('section', 'day', 'hour', 'density')
    list_filter = ('day', 'section', 'density')
    search_fields = ('section__code',)


@admin.register(UserAccount)
class UserAccountAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'employee_id',
        'role',
        'department',
        'phone_number',
        'is_approved',
        'created_at',
        'last_login_at',
    )
    list_filter = ('role', 'is_approved', 'department')
    search_fields = ('user__username', 'user__email', 'employee_id', 'department')
    readonly_fields = ('created_at', 'last_login_at')
