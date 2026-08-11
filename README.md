# Event Photo Hub

A Django application that lets event organizers upload bulk photos, auto-detect faces via Celery workers, and let guests find their own photos by scanning a QR code and uploading a selfie.

## Tech Stack

- Python 3.11+, Django 5.x, Django REST Framework
- MongoDB via djongo
- Celery + Redis (background face detection & matching)
- `face_recognition` (dlib-based) for face encoding & comparison
- Bootstrap 5 (mobile-first guest UI)
- Pillow for thumbnails, `qrcode` for QR generation

---

## Prerequisites

> **Windows note:** `dlib` (required by `face_recognition`) is notoriously difficult to build on Windows natively. Use WSL2 for local development.

**System deps (Ubuntu/Debian / WSL2):**

```bash
sudo apt-get update && sudo apt-get install -y \
  cmake build-essential libopenblas-dev liblapack-dev \
  python3-dev libx11-dev
```

**Python env:**

```bash
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**MongoDB:** Install MongoDB 7 locally or use a MongoDB Atlas free tier. Set connection details in `.env`.

**Redis:**

```bash
sudo apt-get install redis-server
sudo systemctl start redis
```

---

## Setup & Run

```bash
cp .env.example .env   # fill in MONGO_* and SECRET_KEY
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

In a second terminal (Celery worker):

```bash
celery -A config worker --loglevel=info
```

Visit http://localhost:8000 and log in.

---

## Environment Variables

Copy `.env.example` → `.env` and fill in:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for dev |
| `MONGO_HOST` | MongoDB host (default `localhost`) |
| `MONGO_PORT` | MongoDB port (27017) |
| `MONGO_USER` | MongoDB username |
| `MONGO_PASSWORD` | MongoDB password |
| `MONGO_DB` | Database name |
| `REDIS_URL` | Redis URL |
| `CELERY_BROKER_URL` | Celery broker (Redis) |
| `CELERY_RESULT_BACKEND` | Celery results backend |
| `FACE_MATCH_TOLERANCE` | Face match strictness (default 0.5; lower = stricter) |

---

## Usage

### Organizer flow

1. Log in at `/accounts/login/`
2. Create an event via the Dashboard
3. Open the event detail page — a QR code is auto-generated
4. Upload photos (multi-select) — face detection runs in the background
5. Watch the progress badge update via polling
6. Share the QR code or guest link with attendees

### Guest flow

1. Scan QR code (or open the shared link)
2. Tap to take a selfie (camera opens on mobile)
3. Accept the privacy notice and submit
4. Wait ~10–30 s while the system searches
5. View matched photos in a gallery grid; download individually or all as ZIP

---

## Running Tests

```bash
python manage.py test events guests
```

Tests mock `face_recognition` so they run without dlib installed.

---

## Admin

Django admin is at `/admin/`. Key actions:

- **Photos → Re-queue for processing** — reprocess photos whose encoding failed
- **Guest Uploads → Delete selfie & face encoding** — GDPR data minimization after matching is done

---

## Project Structure

```
event_photo_hub/
├── config/          # Django settings, Celery app, URLs
├── accounts/        # Organizer auth (login / register)
├── events/          # Event CRUD, QR generation, organizer dashboard
├── photos/          # EventPhoto model, bulk upload, face encoding tasks
├── guests/          # Guest selfie upload, face matching tasks, results gallery
├── templates/       # HTML templates (base + per-app)
├── static/          # Static assets
├── media/           # Uploaded files (created at runtime)
└── requirements.txt
```
