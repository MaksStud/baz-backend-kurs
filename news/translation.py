from modeltranslation.translator import translator, TranslationOptions
from .models import News


class NewsTranslationOptions(TranslationOptions):
    """News Translation"""
    fields = ('title', 'description')


translator.register(News, NewsTranslationOptions)

