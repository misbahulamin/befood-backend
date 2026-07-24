import uuid

from django.db import models


class PublicIdMixin(models.Model):
    """Opaque public UUID identity; keep integer PK for relations."""

    public_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )

    class Meta:
        abstract = True
