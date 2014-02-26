from django.contrib import admin

from .models import Queue
from .models import QueueEntry


class QueueEntryAdmin(admin.ModelAdmin):
    date_hierarchy = 'time_completed'
    list_display = (
        'queue',
        'key',
        'sort_key',
        'time_added',
        'is_complete',
        'time_completed',
    )
    list_filter = (
        'queue',
        'is_complete',
    )
    list_editable = (
        'is_complete',
    )


class QueueEntryInline(admin.TabularInline):
    model = QueueEntry


class QueueAdmin(admin.ModelAdmin):
    list_display = (
        'name',
    )
    inlines = [QueueEntryInline]

admin.site.register(QueueEntry, QueueEntryAdmin)
admin.site.register(Queue, QueueAdmin)
