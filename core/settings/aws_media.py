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
    """Require bucket + region when S3 media is enabled. Access keys are optional (IAM role)."""
    missing = []
    if not bucket_name:
        missing.append('AWS_STORAGE_BUCKET_NAME')
    if not region_name:
        missing.append('AWS_S3_REGION_NAME')
    if missing:
        raise ImproperlyConfigured(
            'S3 media storage requires: ' + ', '.join(missing)
        )


def build_s3_media_url(
    *,
    bucket_name: str,
    region_name: str,
    custom_domain: str = '',
) -> str:
    """
    Build MEDIA_URL for S3-backed media.

    Prefer AWS_S3_CUSTOM_DOMAIN when set; otherwise the regional bucket endpoint.
    """
    domain = (custom_domain or '').strip().rstrip('/')
    if domain:
        if domain.startswith('https://') or domain.startswith('http://'):
            return domain if domain.endswith('/') else f'{domain}/'
        return f'https://{domain}/'
    return f'https://{bucket_name}.s3.{region_name}.amazonaws.com/'
