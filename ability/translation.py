from modeltranslation.translator import translator, TranslationOptions
from .models import Wish


class WishTranslationOptions(TranslationOptions):
    """Wish Translation"""
    fields = ('name', 'description', 'additional_description')


translator.register(Wish, WishTranslationOptions)

