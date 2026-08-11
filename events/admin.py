from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'created_by', 'event_date', 'total_photos', 'processed_photos', 'created_at']
    list_filter = ['event_date', 'created_by']
    search_fields = ['name', 'slug']
    readonly_fields = ['slug', 'qr_code', 'created_at']
