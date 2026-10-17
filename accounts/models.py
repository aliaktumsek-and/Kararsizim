from django.contrib.auth.models import AbstractUser
from django.core.validators import MinLengthValidator, RegexValidator
from django.db import models
from django.db.models.functions import Lower

USERNAME_MIN_LENGTH = 3
USERNAME_MAX_LENGTH = 20

username_validator = RegexValidator(
    regex=r"^[A-Za-z0-9_]+$",
    message="Kullanıcı adı sadece harf, rakam ve alt çizgi (_) içerebilir.",
)


class User(AbstractUser):
    """Custom user model.

    Username and email are unique case-insensitively (enforced in the database
    through functional unique constraints). The email is required and is never
    exposed publicly; only the username is shown in the UI.
    """

    username = models.CharField(
        max_length=USERNAME_MAX_LENGTH,
        unique=True,
        validators=[MinLengthValidator(USERNAME_MIN_LENGTH), username_validator],
        error_messages={"unique": "Bu kullanıcı adı zaten alınmış."},
    )
    email = models.EmailField(
        unique=True,
        error_messages={"unique": "Bu e-posta adresi zaten kayıtlı."},
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("username"), name="user_username_ci_unique"),
            models.UniqueConstraint(Lower("email"), name="user_email_ci_unique"),
        ]

    def __str__(self):
        return self.username
