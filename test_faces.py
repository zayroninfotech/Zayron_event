import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

import cv2
from insightface.app import FaceAnalysis
from photos.models import EventPhoto

app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
app.prepare(ctx_id=-1, det_size=(640, 640))

print('\n--- Testing first 10 photos ---')
for p in EventPhoto.objects.all()[:10]:
    img = cv2.imread(p.image.path)
    if img is None:
        print(f'  {p.pk} CANNOT READ: {p.image.path}')
        continue
    h, w = img.shape[:2]
    faces = app.get(img)
    name = p.image.name.split('/')[-1][:45]
    print(f'  {p.pk} | {w}x{h} | {len(faces)} face(s) | {name}')
