from django.db import models


class RateLimitHit(models.Model):
    """One counted request, stored as a keyed hash and a timestamp only.

    `key_hash` is an HMAC of the limited key (an IP address, a user id or a login
    identifier), so neither the raw value nor anything linking it to a vote or a
    person is stored. Rows are pruned automatically after a day.
    """

    scope = models.CharField(max_length=40)
    key_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        indexes = [models.Index(fields=["scope", "key_hash", "created_at"], name="ratelimit_lookup_idx")]

    def __str__(self):
        return f"{self.scope}:{self.key_hash[:8]}"
