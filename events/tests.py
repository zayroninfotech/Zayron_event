from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from unittest.mock import patch
from datetime import date
from .models import Event

User = get_user_model()


class EventModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('organizer', password='pass')

    @patch.object(Event, '_generate_qr_code')
    def test_slug_auto_generated(self, mock_qr):
        event = Event.objects.create(
            name='Summer Wedding',
            event_date=date.today(),
            created_by=self.user,
        )
        self.assertEqual(event.slug, 'summer-wedding')

    @patch.object(Event, '_generate_qr_code')
    def test_slug_unique(self, mock_qr):
        Event.objects.create(name='Gala', event_date=date.today(), created_by=self.user)
        event2 = Event.objects.create(name='Gala', event_date=date.today(), created_by=self.user)
        self.assertEqual(event2.slug, 'gala-1')

    @patch.object(Event, '_generate_qr_code')
    def test_dashboard_requires_login(self, mock_qr):
        c = Client()
        resp = c.get(reverse('dashboard'))
        self.assertRedirects(resp, '/accounts/login/?next=/dashboard/')

    @patch.object(Event, '_generate_qr_code')
    def test_dashboard_shows_events(self, mock_qr):
        c = Client()
        c.login(username='organizer', password='pass')
        Event.objects.create(name='My Party', event_date=date.today(), created_by=self.user)
        resp = c.get(reverse('dashboard'))
        self.assertContains(resp, 'My Party')
