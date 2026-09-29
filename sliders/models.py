from django.core.validators import MinValueValidator
from django.db import models

from core.models import PublicIdMixin

from sliders.utils.slider_image import slider_image_upload_path


class HomeSlider(PublicIdMixin, models.Model):
    """Home carousel banner managed via verified-admin API."""

    image = models.ImageField(upload_to=slider_image_upload_path)
    priority = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text='Lower values appear first on the home carousel (1 = first).',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['priority', 'created_at', 'id']
        verbose_name = 'home slider'
        verbose_name_plural = 'home sliders'

    def __str__(self):
        return f'slider {self.priority} ({self.public_id})'
