from django.utils import timezone

from onahar.models import OnaharPrivacyPreference


def get_or_create_privacy(customer) -> OnaharPrivacyPreference:
    pref, _ = OnaharPrivacyPreference.objects.get_or_create(customer=customer)
    return pref


def customer_display_name(customer, preference: OnaharPrivacyPreference | None = None) -> str:
    pref = preference or get_or_create_privacy(customer)
    user = customer.user
    full = f'{user.first_name} {user.last_name}'.strip() or user.username or 'Contributor'

    if pref.display_mode == OnaharPrivacyPreference.DisplayMode.ANONYMOUS:
        return 'Anonymous Contributor'
    if pref.display_mode == OnaharPrivacyPreference.DisplayMode.PUBLIC:
        return full
    # partial
    parts = full.split()
    masked = []
    for part in parts:
        if not part:
            continue
        if len(part) == 1:
            masked.append(f'{part}***')
        else:
            masked.append(f'{part[0]}***')
    return ' '.join(masked) if masked else 'Anonymous Contributor'


def current_year_month(when=None) -> str:
    when = when or timezone.localtime()
    return when.strftime('%Y-%m')
