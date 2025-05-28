from rest_framework import serializers

from .models import News


class NewsSerializers(serializers.ModelSerializer):
    class Meta:
        model = News
        fields = ['photo', 'slug', 'title_uk', 'title_en', 'description_uk', 'description_en']