from rest_framework import serializers

from .models import Brand


class BrandSerializer(serializers.ModelSerializer):
    """Serializer for Brand"""
    class Meta:
        model = Brand
        fields = ['slug', 'nickname', 'photo',  'cover_photo', 'name_uk', 'name_en', 'description_uk', 'description_en']
