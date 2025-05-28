"""Contains model abstractions to use in other apps."""
from django.db import models


class Slug(models.Model):
    """Abstract model that contain slug field."""
    slug = models.CharField(max_length=128, unique=True, null=True)

    class Meta:
        abstract = True
