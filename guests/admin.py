from django.contrib import admin
from .models import GuestUpload, PhotoMatch


@admin.register(GuestUpload)
class GuestUploadAdmin(admin.ModelAdmin):
    list_display = ['id', 'event', 'name', 'phone', 'status', 'created_at']
    list_filter = ['status', 'event']
    readonly_fields = ['face_encoding', 'task_id', 'created_at']
    actions = ['delete_biometric_data']

    @admin.action(description='Delete selfie & face encoding (data minimization)')
    def delete_biometric_data(self, request, queryset):
        for upload in queryset:
            upload.delete_biometric_data()
        self.message_user(request, f'Biometric data wiped for {queryset.count()} upload(s).')


@admin.register(PhotoMatch)
class PhotoMatchAdmin(admin.ModelAdmin):
    list_display = ['id', 'guest_upload', 'photo', 'confidence']
    list_filter = ['guest_upload__event']
    readonly_fields = ['confidence']
