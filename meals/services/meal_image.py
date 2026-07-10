import os
from datetime import datetime

from django.utils.text import slugify

ALLOWED_EXTENSIONS = ('jpg', 'jpeg', 'png', 'webp')
MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024


def validate_image_extension(filename):
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(ALLOWED_EXTENSIONS)
        raise ValueError(f'Invalid image extension. Allowed extensions: {allowed}.')
    return ext


def validate_image_size(file_obj):
    if file_obj.size > MAX_IMAGE_SIZE_BYTES:
        raise ValueError('Image size must not exceed 5MB.')
    return file_obj


def generate_meal_thumbnail_filename(meal_name, original_filename):
    ext = validate_image_extension(original_filename)
    slug = slugify(meal_name) or 'meal'
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    return f'{slug}-{timestamp}.{ext}'


def meal_thumbnail_upload_path(instance, filename):
    meal_name = instance.meal_name or 'meal'
    safe_filename = generate_meal_thumbnail_filename(meal_name, filename)
    return f'meals/thumbnails/{safe_filename}'
