import os
from django.db import models
from events.models import Event


def event_photo_path(instance, filename):
    return f'event_photos/{instance.event.slug}/{filename}'


def event_thumb_path(instance, filename):
    return f'event_photos/{instance.event.slug}/thumbs/{filename}'


class EventPhoto(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to=event_photo_path)
    thumbnail = models.ImageField(upload_to=event_thumb_path, blank=True, null=True)
    face_encodings = models.JSONField(default=list, blank=True)
    processed = models.BooleanField(default=False)
    face_count = models.IntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'{self.event.name} - {os.path.basename(self.image.name)}'

    @property
    def filename(self):
        return os.path.basename(self.image.name)
