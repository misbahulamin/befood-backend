"""Shared Befood branding context for customer auth emails."""

from django.conf import settings


BRAND_YELLOW = '#FFD100'
BRAND_DEEP_INK = '#1C1A17'
BRAND_WARM_WHITE = '#FDFCF8'
BRAND_NAME = 'Befood'
BRAND_TAGLINE = "Homestyle meals, every day — ঘরের স্বাদের খাবার"


def _honorific_for_gender(gender):
    if gender == 'male':
        return 'bhaiya'
    if gender == 'female':
        return 'apu'
    return 'bhaiya/apu'


def build_greeting(user, profile=None):
    """
    Return Bangla-honorific greeting for auth emails.

    Examples:
    - Hello Rahim bhaiya
    - Hello Ayesha apu
    - Hello bhaiya/apu
    """
    first_name = (getattr(user, 'first_name', None) or '').strip()
    if profile is None:
        profile = getattr(user, 'customer_profile', None)
    gender = getattr(profile, 'gender', None) if profile is not None else None
    honorific = _honorific_for_gender(gender)
    if first_name:
        return f'Hello {first_name} {honorific}'
    return f'Hello {honorific}'


def _whatsapp_me_url(whatsapp_display):
    digits = ''.join(ch for ch in (whatsapp_display or '') if ch.isdigit())
    if not digits:
        return ''
    return f'https://wa.me/{digits}'


def build_brand_email_context(user, *, extra=None):
    """Build shared template context for branded auth emails."""
    profile = getattr(user, 'customer_profile', None)
    frontend_url = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    whatsapp = getattr(settings, 'EMAIL_WHATSAPP', '')
    context = {
        'user': user,
        'recipient_email': user.email,
        'greeting': build_greeting(user, profile),
        'brand_name': BRAND_NAME,
        'brand_tagline': BRAND_TAGLINE,
        'brand_yellow': BRAND_YELLOW,
        'brand_deep_ink': BRAND_DEEP_INK,
        'brand_warm_white': BRAND_WARM_WHITE,
        'logo_url': getattr(settings, 'EMAIL_LOGO_URL', ''),
        'play_store_url': getattr(settings, 'EMAIL_PLAY_STORE_URL', ''),
        'play_store_badge_url': getattr(settings, 'EMAIL_PLAY_STORE_BADGE_URL', ''),
        'site_url': getattr(settings, 'EMAIL_SITE_URL', frontend_url),
        'phone': getattr(settings, 'EMAIL_PHONE', ''),
        'whatsapp': whatsapp,
        'whatsapp_url': _whatsapp_me_url(whatsapp),
        'facebook_url': getattr(settings, 'EMAIL_FACEBOOK_URL', ''),
        'instagram_url': getattr(settings, 'EMAIL_INSTAGRAM_URL', ''),
        'facebook_icon_url': getattr(settings, 'EMAIL_FACEBOOK_ICON_URL', ''),
        'instagram_icon_url': getattr(settings, 'EMAIL_INSTAGRAM_ICON_URL', ''),
        'whatsapp_icon_url': getattr(settings, 'EMAIL_WHATSAPP_ICON_URL', ''),
        'address': getattr(settings, 'EMAIL_ADDRESS', ''),
        'frontend_url': frontend_url,
    }
    if extra:
        context.update(extra)
    return context


def build_password_reset_link(uidb64, token):
    frontend_url = getattr(settings, 'FRONTEND_URL', '').rstrip('/')
    path = getattr(settings, 'PASSWORD_RESET_FRONTEND_PATH', '/reset-password')
    if not path.startswith('/'):
        path = f'/{path}'
    return f'{frontend_url}{path}?uid={uidb64}&token={token}'
