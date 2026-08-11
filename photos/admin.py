from django.contrib import admin
from .models import EventPhoto


@admin.register(EventPhoto)
class EventPhotoAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'event', 'processed', 'face_count', 'uploaded_at']
    list_filter = ['processed', 'event']
    readonly_fields = ['face_encodings', 'processed', 'face_count', 'uploaded_at']
    actions = ['reprocess_photos']

    @admin.action(description='Re-queue selected photos for face processing')
    def reprocess_photos(self, request, queryset):
        from .tasks import process_event_photo
        for photo in queryset:
            photo.processed = False
            photo.face_encodings = []
            photo.save()
            process_event_photo.delay(photo.pk)
        self.message_user(request, f'{queryset.count()} photo(s) queued for reprocessing.')
