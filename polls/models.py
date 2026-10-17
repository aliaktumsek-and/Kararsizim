from django.conf import settings
from django.db import models

QUESTION_MAX_LENGTH = 140
OPTION_MAX_LENGTH = 60
MIN_OPTIONS = 2
MAX_OPTIONS = 5


class Poll(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls")
    question = models.CharField(max_length=QUESTION_MAX_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.question


class Option(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="options")
    text = models.CharField(max_length=OPTION_MAX_LENGTH)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.text


class Vote(models.Model):
    """A single vote. `user` is NULL for anonymous votes.

    No IP, device or other tracking data is stored on purpose.
    """

    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    option = models.ForeignKey(Option, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="votes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["poll", "user"],
                condition=models.Q(user__isnull=False),
                name="vote_one_per_user_per_poll",
            ),
        ]

    def __str__(self):
        return f"{self.user or 'anonymous'} -> {self.option_id}"
