from django.contrib.auth.models import AbstractUser
from django_mongodb_backend.fields import ObjectIdAutoField


class User(AbstractUser):
    """Custom user model using MongoDB ObjectId as primary key."""
    id = ObjectIdAutoField(primary_key=True)

    class Meta(AbstractUser.Meta):
        swappable = 'AUTH_USER_MODEL'

    def __str__(self):
        return self.username
