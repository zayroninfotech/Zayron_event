from django.test import TestCase
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from datetime import date
import numpy as np

User = get_user_model()


def _make_event(user, name='Test Event'):
    from events.models import Event
    with patch.object(Event, '_generate_qr_code'):
        return Event.objects.create(name=name, event_date=date.today(), created_by=user)


class FaceMatchingTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('org', password='pass')
        self.event = _make_event(self.user)

    def _make_photo(self, encodings):
        from photos.models import EventPhoto
        photo = EventPhoto(event=self.event, processed=True, face_count=len(encodings))
        photo.face_encodings = [e.tolist() for e in encodings]
        photo.image = 'event_photos/test/fake.jpg'
        photo.save()
        return photo

    def _make_upload(self):
        from guests.models import GuestUpload
        upload = GuestUpload(event=self.event, status='pending')
        upload.selfie = 'selfies/test/fake.jpg'
        upload.save()
        return upload

    @patch('guests.tasks.face_recognition')
    def test_matching_finds_close_faces(self, mock_fr):
        """A guest encoding within tolerance should create a PhotoMatch."""
        from guests.tasks import match_guest_faces
        from guests.models import PhotoMatch

        enc_a = np.random.rand(128).astype(np.float64)
        enc_b = enc_a + 0.01  # very close — same person

        photo = self._make_photo([enc_a])
        upload = self._make_upload()

        mock_fr.load_image_file.return_value = MagicMock()
        mock_fr.face_encodings.return_value = [enc_b]
        mock_fr.face_distance.return_value = np.array([np.linalg.norm(enc_a - enc_b)])

        match_guest_faces(upload.pk)

        upload.refresh_from_db()
        self.assertEqual(upload.status, 'done')
        self.assertEqual(PhotoMatch.objects.filter(guest_upload=upload, photo=photo).count(), 1)

    @patch('guests.tasks.face_recognition')
    def test_no_match_for_distant_faces(self, mock_fr):
        """A guest encoding outside tolerance should produce zero matches."""
        from guests.tasks import match_guest_faces
        from guests.models import PhotoMatch

        enc_a = np.zeros(128)
        enc_b = np.ones(128)  # very far away

        photo = self._make_photo([enc_a])
        upload = self._make_upload()

        mock_fr.load_image_file.return_value = MagicMock()
        mock_fr.face_encodings.return_value = [enc_b]
        mock_fr.face_distance.return_value = np.array([np.linalg.norm(enc_a - enc_b)])

        match_guest_faces(upload.pk)

        upload.refresh_from_db()
        self.assertEqual(upload.status, 'done')
        self.assertEqual(PhotoMatch.objects.filter(guest_upload=upload).count(), 0)

    @patch('guests.tasks.face_recognition')
    def test_no_face_in_selfie(self, mock_fr):
        """When selfie has no detectable face, status → done with zero matches."""
        from guests.tasks import match_guest_faces
        from guests.models import PhotoMatch

        upload = self._make_upload()
        mock_fr.load_image_file.return_value = MagicMock()
        mock_fr.face_encodings.return_value = []

        match_guest_faces(upload.pk)

        upload.refresh_from_db()
        self.assertEqual(upload.status, 'done')
        self.assertEqual(PhotoMatch.objects.filter(guest_upload=upload).count(), 0)

    def test_delete_biometric_data(self):
        """delete_biometric_data wipes encoding and selfie field."""
        from guests.models import GuestUpload
        upload = GuestUpload.objects.create(
            event=self.event,
            face_encoding=[0.1, 0.2, 0.3],
            status='done',
        )
        with patch.object(upload.selfie, 'delete', return_value=None):
            upload.delete_biometric_data()
        upload.refresh_from_db()
        self.assertEqual(upload.face_encoding, [])
