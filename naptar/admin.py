"""
Django Admin regisztráció — magyar feliratokkal, kereséssel, szűréssel.
"""

from django.contrib import admin
from django.utils import timezone
from .models import Job, WorkSchedule, TimeOff, Settings, DayOverride


class WorkScheduleInline(admin.TabularInline):
    model = WorkSchedule
    extra = 0
    fields = ['start_datetime', 'end_datetime', 'hours', 'is_auto_scheduled', 'note']
    readonly_fields = ['hours']


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ['title', 'client_name', 'location', 'estimated_hours',
                    'remaining_hours_display', 'scheduled_hours_display',
                    'progress_bar', 'deadline', 'priority', 'status', 'created_at']
    list_display_links = ['title']
    list_filter = ['status', 'priority', 'created_at']
    list_editable = ['status', 'priority']
    search_fields = ['title', 'client_name', 'location', 'description']
    ordering = ['-created_at']
    inlines = [WorkScheduleInline]

    fieldsets = (
        ("Munka adatok", {
            'fields': ['title', 'description', 'client_name', 'location']
        }),
        ("Időzítés", {
            'fields': ['estimated_hours', 'remaining_hours',
                       'earliest_start_date', 'deadline']
        }),
        ("Státusz és prioritás", {
            'fields': ['priority', 'status']
        }),
    )
    readonly_fields = ['remaining_hours']

    @admin.display(description="Hátralévő óra")
    def remaining_hours_display(self, obj):
        return f"{obj.remaining_hours:.1f} ó"

    @admin.display(description="Beosztva")
    def scheduled_hours_display(self, obj):
        return f"{obj.scheduled_hours:.1f} ó"

    @admin.display(description="Kész")
    def progress_bar(self, obj):
        pct = obj.progress_percent
        bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
        return f"{bar} {pct}%"


@admin.register(WorkSchedule)
class WorkScheduleAdmin(admin.ModelAdmin):
    list_display = ['job_link', 'start_datetime', 'end_datetime',
                    'hours', 'is_auto_scheduled', 'note']
    list_display_links = ['job_link']
    list_filter = ['is_auto_scheduled', 'start_datetime']
    search_fields = ['job__title', 'job__client_name', 'note']
    ordering = ['-start_datetime']
    autocomplete_fields = ['job']

    @admin.display(description="Munka")
    def job_link(self, obj):
        return str(obj.job)


@admin.register(TimeOff)
class TimeOffAdmin(admin.ModelAdmin):
    list_display = ['title', 'start_datetime', 'end_datetime', 'reason']
    list_filter = ['start_datetime']
    search_fields = ['title', 'reason']
    ordering = ['-start_datetime']


@admin.register(Settings)
class SettingsAdmin(admin.ModelAdmin):
    """
    Beállítások — naponkénti munkaidő.
    Egyetlen rekord, az Add gomb letiltva.
    """

    fieldsets = (
        ("Hétfő", {
            'fields': ['mon_active', ('mon_start', 'mon_end')]
        }),
        ("Kedd", {
            'fields': ['tue_active', ('tue_start', 'tue_end')]
        }),
        ("Szerda", {
            'fields': ['wed_active', ('wed_start', 'wed_end')]
        }),
        ("Csütörtök", {
            'fields': ['thu_active', ('thu_start', 'thu_end')]
        }),
        ("Péntek", {
            'fields': ['fri_active', ('fri_start', 'fri_end')]
        }),
        ("Szombat", {
            'fields': ['sat_active', ('sat_start', 'sat_end')]
        }),
        ("Vasárnap", {
            'fields': ['sun_active', ('sun_start', 'sun_end')]
        }),
        ("Korlátozások", {
            'fields': ['max_daily_hours', 'min_schedule_block_hours']
        }),
    )

    def has_add_permission(self, request):
        return not Settings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DayOverride)
class DayOverrideAdmin(admin.ModelAdmin):
    list_display = ['date', 'is_workday', 'start_time', 'end_time', 'note']
    list_filter = ['is_workday', 'date']
    search_fields = ['note']
    ordering = ['-date']
