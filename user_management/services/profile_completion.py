from ..models import CustomerAddress, CustomerProfile

COMPLETION_THRESHOLD = 80

IMPORTANT_FIELDS = (
    'birth_date',
    'gender',
    'delivery_address',
    'emergency_contact_phone',
    'organization_name',
    'allergy_info',
    'restricted_foods',
    'preferred_food_type',
    'religious',
    'preferred_delivery_time',
)


def _is_field_completed(profile, field_name):
    if field_name == 'birth_date':
        return profile.birth_date is not None
    if field_name == 'gender':
        return bool(profile.gender)
    if field_name == 'delivery_address':
        from user_management.models import MealDeliveryPreference

        pref = MealDeliveryPreference.objects.filter(customer_profile=profile).first()
        if pref and (pref.lunch_place_id or pref.dinner_place_id):
            return True
        if profile.delivery_places.filter(is_active=True).exists():
            return True
        # Transition fallback: legacy present default delivery address.
        return profile.addresses.filter(
            address_type=CustomerAddress.AddressType.PRESENT,
            is_default_delivery=True,
        ).exists()
    if field_name == 'emergency_contact_phone':
        return bool(profile.emergency_contact_phone)
    if field_name == 'organization_name':
        return bool(profile.organization_name)
    if field_name == 'allergy_info':
        if profile.has_allergy:
            return bool(profile.allergy_details and profile.allergy_details.strip())
        return True
    if field_name == 'restricted_foods':
        return bool(profile.restricted_foods and profile.restricted_foods.strip())
    if field_name == 'preferred_food_type':
        return bool(profile.preferred_food_type)
    if field_name == 'religious':
        return bool(profile.religious)
    if field_name == 'preferred_delivery_time':
        return profile.preferred_delivery_time is not None
    return False


def calculate_profile_completion(profile):
    total = len(IMPORTANT_FIELDS)
    completed = sum(1 for field in IMPORTANT_FIELDS if _is_field_completed(profile, field))
    percentage = int(round((completed / total) * 100)) if total else 0
    return percentage, percentage >= COMPLETION_THRESHOLD


def update_profile_completion(profile):
    percentage, is_completed = calculate_profile_completion(profile)
    profile.profile_completion_percentage = percentage
    profile.profile_completed = is_completed
    profile.save(update_fields=['profile_completion_percentage', 'profile_completed', 'updated_at'])
    return profile
