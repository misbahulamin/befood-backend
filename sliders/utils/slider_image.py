import os
import uuid
from datetime import datetime

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


def slider_image_upload_path(instance, filename):
    ext = validate_image_extension(filename)
    stamp = datetime.now().strftime('%Y/%m')
    return f'home_sliders/{stamp}/{uuid.uuid4().hex}.{ext}'
