from django.db import transaction

ONBOARDING_FIELDS = (
    'first_name',
    'last_name',
    'phone',
    'occupation',
    'is_bachelor',
    'gender',
)

# Product Profile Completion form gate (mobile). Distinct from ONBOARDING_FIELDS
# and from extended CustomerProfile.profile_completed (food/emergency metrics).
# Email is intentionally NOT required for phone-first Home skip.
PRODUCT_PROFILE_FIELDS = (
    'first_name',
    'birth_date',
    'gender',
)


def _is_name_present(value):
    return bool(value and str(value).strip())


def _is_onboarding_field_present(user, profile, field_name):
    if field_name == 'first_name':
        return _is_name_present(user.first_name)
    if field_name == 'last_name':
        return _is_name_present(user.last_name)
    if field_name == 'phone':
        return bool(profile.is_phone_verified)
    if field_name == 'occupation':
        return bool(profile.occupation)
    if field_name == 'is_bachelor':
        return profile.is_bachelor is not None
    if field_name == 'gender':
        return bool(profile.gender)
    return False


def _is_product_field_present(user, profile, field_name):
    if field_name == 'first_name':
        return _is_name_present(user.first_name)
    if field_name == 'birth_date':
        return profile.birth_date is not None
    if field_name == 'gender':
        return bool(profile.gender and str(profile.gender).strip())
    return False


def get_onboarding_completion(user, profile=None):
    """Derive onboarding completion from User + CustomerProfile values."""
    if profile is None:
        profile = user.customer_profile
    missing_fields = [
        field for field in ONBOARDING_FIELDS if not _is_onboarding_field_present(user, profile, field)
    ]
    total = len(ONBOARDING_FIELDS)
    populated = total - len(missing_fields)
    percentage = int(round((populated / total) * 100)) if total else 0
    return {
        'completed': len(missing_fields) == 0,
        'missing_fields': missing_fields,
        'completion_percentage': percentage,
    }


def get_product_profile_completion(user, profile=None):
    """
    Computed product-profile completeness for mobile post-auth routing.

    Required: non-empty first_name, non-null birth_date, non-empty gender.
    Email is not required (phone-first accounts may skip Home without email).
    Does not use extended ``profile_completed``.
    """
    if profile is None:
        profile = user.customer_profile
    missing_fields = [
        field
        for field in PRODUCT_PROFILE_FIELDS
        if not _is_product_field_present(user, profile, field)
    ]
    return {
        'completed': len(missing_fields) == 0,
        'missing_fields': missing_fields,
    }


@transaction.atomic
def update_customer_onboarding_profile(profile, validated_data):
    """Persist onboarding + extended profile fields immediately."""
    user = profile.user
    user_updates = {}
    if 'first_name' in validated_data:
        user_updates['first_name'] = validated_data.pop('first_name')
    if 'last_name' in validated_data:
        user_updates['last_name'] = validated_data.pop('last_name')
    if user_updates:
        for attr, value in user_updates.items():
            setattr(user, attr, value)
        user.save(update_fields=[*user_updates.keys()])

    for attr, value in validated_data.items():
        setattr(profile, attr, value)
    profile.save()
    return profile
