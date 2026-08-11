from django.db import models
from events.models import Event
from photos.models import EventPhoto


def selfie_upload_path(instance, filename):
    return f'selfies/{instance.event.slug}/{filename}'


class GuestUpload(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='guest_uploads')
    selfie = models.ImageField(upload_to=selfie_upload_path, null=True, blank=True)
    face_encoding = models.JSONField(default=list, blank=True)
    name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    task_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('pending', 'Pending'), ('processing', 'Processing'), ('done', 'Done'), ('failed', 'Failed')],
        default='pending',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Guest upload for {self.event.name} at {self.created_at:%Y-%m-%d %H:%M}'

    def delete_biometric_data(self):
        """Data-minimization: wipe selfie and encoding after matching."""
        if self.selfie:
            self.selfie.delete(save=False)
            self.selfie = None
        self.face_encoding = []
        self.save(update_fields=['selfie', 'face_encoding'])


class PhotoMatch(models.Model):
    guest_upload = models.ForeignKey(GuestUpload, on_delete=models.CASCADE, related_name='matches')
    photo = models.ForeignKey(EventPhoto, on_delete=models.CASCADE, related_name='matches')
    confidence = models.FloatField()

    class Meta:
        unique_together = ('guest_upload', 'photo')
        ordering = ['confidence']

    def __str__(self):
        return f'Match: guest {self.guest_upload_id} → photo {self.photo_id} ({self.confidence:.3f})'
