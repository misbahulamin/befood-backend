import os
import re

from django.core.files.storage import default_storage
from django.db import transaction

ALLOWED_EXTENSIONS = ('jpg', 'jpeg', 'png', 'webp')
MAX_IMAGE_SIZE_BYTES = 2 * 1024 * 1024


def validate_image_extension(filename):
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(ALLOWED_EXTENSIONS)
        raise ValueError(f'Invalid image extension. Allowed extensions: {allowed}.')
    return ext


def validate_image_size(file_obj):
    size = getattr(file_obj, 'size', None)
    if size is not None and size > MAX_IMAGE_SIZE_BYTES:
        raise ValueError('Image size must not exceed 2MB.')
    return file_obj


def _sanitize_slug(raw):
    value = (raw or '').strip().lower()
    value = value.replace(' ', '_')
    value = re.sub(r'[^a-z0-9_]+', '_', value)
    value = re.sub(r'_+', '_', value).strip('_')
    return value or 'user'


def build_profile_folder_slug(user, public_id):
    """
    Build a collision-safe folder slug: {name_or_email}_{public_id8}.
    """
    full_name = ' '.join(
        part for part in (getattr(user, 'first_name', ''), getattr(user, 'last_name', '')) if part
    ).strip()
    if full_name:
        base = _sanitize_slug(full_name)
    else:
        email = getattr(user, 'email', '') or ''
        local_part = email.split('@', 1)[0] if email else ''
        base = _sanitize_slug(local_part)

    short_id = str(public_id).replace('-', '')[:8]
    return f'{base}_{short_id}'


def profile_picture_upload_path(instance, filename):
    ext = validate_image_extension(filename)
    user = instance.user
    folder = build_profile_folder_slug(user, instance.public_id)
    return f'profiles/users/{folder}/profile_picture.{ext}'


def get_profile_picture_url(profile, request=None):
    picture = getattr(profile, 'profile_picture', None)
    if not picture or not getattr(picture, 'name', None):
        return None
    try:
        url = picture.url
    except ValueError:
        return None
    if request is not None and url and not url.startswith(('http://', 'https://')):
        return request.build_absolute_uri(url)
    return url


def _delete_storage_file(name):
    if not name:
        return
    try:
        if default_storage.exists(name):
            default_storage.delete(name)
    except Exception:
        # Best-effort cleanup; missing keys / remote errors must not block the API.
        pass


@transaction.atomic
def upload_profile_picture(profile, file_obj):
    validate_image_extension(getattr(file_obj, 'name', '') or 'upload.jpg')
    validate_image_size(file_obj)

    old_name = profile.profile_picture.name if profile.profile_picture else None
    # Delete first so storage can reuse the canonical profile_picture.{ext} key.
    if old_name:
        profile.profile_picture = None
        profile.save(update_fields=['profile_picture', 'updated_at'])
        _delete_storage_file(old_name)

    profile.profile_picture = file_obj
    profile.save(update_fields=['profile_picture', 'updated_at'])

    return get_profile_picture_url(profile)


@transaction.atomic
def clear_profile_picture(profile):
    old_name = profile.profile_picture.name if profile.profile_picture else None
    if not old_name:
        return None
    profile.profile_picture = None
    profile.save(update_fields=['profile_picture', 'updated_at'])
    _delete_storage_file(old_name)
    return None
