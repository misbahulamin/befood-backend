from django.core.exceptions import ImproperlyConfigured

PROD_STORAGES = {
    'default': {
        'BACKEND': 'core.storage.S3MediaStorage',
    },
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
    },
}

LOCAL_S3_STORAGES = {
    'default': {
        'BACKEND': 'core.storage.S3MediaStorage',
    },
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


def validate_aws_media_settings(*, bucket_name: str, region_name: str) -> None:
    missing = []
    if not bucket_name:
        missing.append('AWS_STORAGE_BUCKET_NAME')
    if not region_name:
        missing.append('AWS_S3_REGION_NAME')
    if missing:
        raise ImproperlyConfigured(
            'Production media storage requires: ' + ', '.join(missing)
        )
