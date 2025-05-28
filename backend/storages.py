import os

from storages.backends.s3boto3 import S3Boto3Storage

SERVER_DOMAIN = os.getenv('SERVER_DOMAIN', 'localhost:8000')


class CustomS3Boto3Storage(S3Boto3Storage):
    custom_domain = f'{SERVER_DOMAIN}/media'
