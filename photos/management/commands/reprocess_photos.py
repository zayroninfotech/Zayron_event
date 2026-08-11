from django.core.management.base import BaseCommand
from photos.models import EventPhoto
from photos.tasks import process_event_photo
import mongo_store


class Command(BaseCommand):
    help = 'Re-process all event photos with ArcFace embeddings'

    def add_arguments(self, parser):
        parser.add_argument('--event-id', type=int, help='Only reprocess photos for this event ID')

    def handle(self, *args, **options):
        qs = EventPhoto.objects.all()
        if options['event_id']:
            qs = qs.filter(event_id=options['event_id'])

        total = qs.count()
        self.stdout.write(f'Resetting and reprocessing {total} photo(s)...')

        # Reset processed flag in SQLite
        qs.update(processed=False, face_count=0)

        # Clear old embeddings in MongoDB
        for photo in qs:
            mongo_store.upsert_photo(photo.pk, {
                'event_id': photo.event_id,
                'image_path': photo.image.name,
                'face_encodings': [],
                'face_count': 0,
                'processed': False,
            })

        # Re-run ArcFace processing for each photo
        for i, photo in enumerate(qs, 1):
            self.stdout.write(f'  [{i}/{total}] Processing photo {photo.pk}...')
            try:
                process_event_photo(photo.pk)
                self.stdout.write(self.style.SUCCESS(f'    Done — {photo.face_count} face(s)'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'    Error: {e}'))

        self.stdout.write(self.style.SUCCESS(f'\nFinished! {total} photos reprocessed with ArcFace.'))
