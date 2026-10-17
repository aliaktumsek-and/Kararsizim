from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

QUESTION_MAX_LENGTH = 140
OPTION_MAX_LENGTH = 60
MIN_OPTIONS = 2
MAX_OPTIONS = 5

# A poll closes by itself this long after it was created, unless its author
# closes it earlier. There is no background job (serverless): the closed state
# is derived from the timestamps whenever it is needed.
POLL_LIFETIME = timedelta(hours=2)


class PollQuerySet(models.QuerySet):
    def closed(self):
        now = timezone.now()
        return self.filter(models.Q(closed_at__isnull=False) | models.Q(created_at__lte=now - POLL_LIFETIME))


class Poll(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="polls")
    question = models.CharField(max_length=QUESTION_MAX_LENGTH)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    # Set when the author closes the poll before the automatic deadline.
    closed_at = models.DateTimeField(null=True, blank=True)

    objects = PollQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.question

    @property
    def expires_at(self):
        return self.created_at + POLL_LIFETIME

    @property
    def is_closed(self):
        return self.closed_at is not None or timezone.now() >= self.expires_at


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
