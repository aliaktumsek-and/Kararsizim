from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model.

    Defined before the first migration so it can be extended safely later.
    Phase 1 adds case-insensitive unique usernames and unique, required emails.
    """

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.username
