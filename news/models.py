from django.db import models

from common.models import Slug


class News(Slug):
    """News model"""
    photo = models.ImageField(upload_to='news_photos/')
    title = models.CharField()
    description = models.TextField()
    priority = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'News'
        verbose_name_plural = 'News'

    def __str__(self) -> str:
        return str(self.title)
