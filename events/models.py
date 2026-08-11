import uuid
import qrcode
import io
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.core.files.base import ContentFile
from django.urls import reverse

User = get_user_model()


def qr_upload_path(instance, filename):
    return f'qr_codes/{instance.slug}/{filename}'


class Event(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, max_length=100, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='events')
    event_date = models.DateField()
    description = models.TextField(blank=True)
    qr_code = models.ImageField(upload_to=qr_upload_path, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(f"{self.name} {self.event_date}")
            slug = base_slug
            n = 1
            while Event.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base_slug}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)
        if not self.qr_code:
            self._generate_qr_code()

    def _generate_qr_code(self):
        guest_url = reverse('guest_landing', kwargs={'slug': self.slug})
        # Build absolute URL with a placeholder host — organizer can share the QR
        # The QR stores just the path; organizer updates host in production
        full_url = f'http://localhost:8000{guest_url}'
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(full_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        filename = f'qr_{self.slug}.png'
        self.qr_code.save(filename, ContentFile(buf.getvalue()), save=True)

    @property
    def total_photos(self):
        return self.photos.count()

    @property
    def processed_photos(self):
        return self.photos.filter(processed=True).count()
