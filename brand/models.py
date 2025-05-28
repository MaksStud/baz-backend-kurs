from django.db import models
from django.core.cache import cache

from common.models import Slug


class Brand(Slug):
    """Model fot Brand"""
    name = models.CharField(max_length=128)
    nickname = models.CharField(max_length=128, unique=True, null=True, blank=True)
    description = models.TextField()
    photo = models.ImageField(upload_to='brand_photos/')
    views_number = models.PositiveIntegerField(blank=True, null=True, default=0)
    cover_photo = models.ImageField(upload_to='brand_photos/', blank=True, null=True,)
    priority = models.IntegerField(default=0)

    def __str__(self) -> str:
        return str(self.nickname)

    def save(self, *args, **kwargs):
        """Deletes data from the cache when used."""
        cache.delete('cache_brands')
        super().save(*args, **kwargs)

