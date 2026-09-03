from django.db import models

DEFAULT_PLAY_STORE_URL = (
    'https://play.google.com/store/apps/details?id=bd.com.befood'
)
DEFAULT_APP_VERSION = '1.0.13'


class AppVersionSettings(models.Model):
    """Singleton: mobile force/optional update policy and store URLs."""

    latest_version = models.CharField(
        max_length=32,
        default=DEFAULT_APP_VERSION,
        help_text='Newest version advertised to clients (semver X.Y.Z).',
    )
    minimum_supported_version = models.CharField(
        max_length=32,
        default=DEFAULT_APP_VERSION,
        help_text='Oldest version allowed without force update (semver X.Y.Z).',
    )
    play_store_url = models.URLField(
        max_length=512,
        default=DEFAULT_PLAY_STORE_URL,
        help_text='Google Play listing URL for Update Now.',
    )
    app_store_url = models.URLField(
        max_length=512,
        blank=True,
        default='',
        help_text='Apple App Store listing URL (optional until iOS publish).',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'App version settings'
        verbose_name_plural = 'App version settings'

    def __str__(self):
        return (
            f'App versions latest={self.latest_version} '
            f'minimum={self.minimum_supported_version}'
        )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls) -> 'AppVersionSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
