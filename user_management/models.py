from django.contrib.auth.models import User
from django.db import models

from core.models import PublicIdMixin


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CustomerProfile(TimeStampedModel):
    class Occupation(models.TextChoices):
        STUDENT = 'student', 'Student'
        JOB_HOLDER = 'job_holder', 'Job Holder'
        FREELANCER = 'freelancer', 'Freelancer'
        BUSINESS_OWNER = 'business_owner', 'Business Owner'
        UNEMPLOYED = 'unemployed', 'Unemployed'
        OTHER = 'other', 'Other'

    class Gender(models.TextChoices):
        MALE = 'male', 'Male'
        FEMALE = 'female', 'Female'
        OTHER = 'other', 'Other'
        PREFER_NOT_TO_SAY = 'prefer_not_to_say', 'Prefer not to say'

    class PreferredFoodType(models.TextChoices):
        REGULAR = 'regular', 'Regular'
        VEGETARIAN = 'vegetarian', 'Vegetarian'
        NON_VEGETARIAN = 'non_vegetarian', 'Non Vegetarian'
        HALAL = 'halal', 'Halal'
        LOW_SPICY = 'low_spicy', 'Low Spicy'
        HIGH_PROTEIN = 'high_protein', 'High Protein'
        DIABETIC_FRIENDLY = 'diabetic_friendly', 'Diabetic Friendly'
        CUSTOM = 'custom', 'Custom'

    class SpiceLevel(models.TextChoices):
        NO_SPICE = 'no_spice', 'No Spice'
        MILD = 'mild', 'Mild'
        MEDIUM = 'medium', 'Medium'
        SPICY = 'spicy', 'Spicy'

    class Religion(models.TextChoices):
        ISLAM = 'islam', 'Islam'
        HINDUISM = 'hinduism', 'Hinduism'
        BUDDHISM = 'buddhism', 'Buddhism'
        CHRISTIANITY = 'christianity', 'Christianity'
        OTHER = 'other', 'Other'
        PREFER_NOT_TO_SAY = 'prefer_not_to_say', 'Prefer not to say'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    phone = models.CharField(max_length=10, unique=True)
    occupation = models.CharField(max_length=30, choices=Occupation.choices)
    is_bachelor = models.BooleanField()
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    emergency_contact_name = models.CharField(max_length=100, null=True, blank=True)
    emergency_contact_phone = models.CharField(max_length=10, null=True, blank=True)

    organization_name = models.CharField(max_length=255, null=True, blank=True)
    academic_year_or_position = models.CharField(max_length=100, null=True, blank=True)

    has_allergy = models.BooleanField(default=False)
    allergy_details = models.TextField(blank=True)
    restricted_foods = models.TextField(blank=True)
    preferred_food_type = models.CharField(
        max_length=30, choices=PreferredFoodType.choices, null=True, blank=True
    )
    spice_level = models.CharField(max_length=20, choices=SpiceLevel.choices, null=True, blank=True)
    religious = models.CharField(max_length=30, choices=Religion.choices, null=True, blank=True)

    delivery_instruction = models.TextField(blank=True)
    preferred_delivery_time = models.TimeField(null=True, blank=True)

    profile_completed = models.BooleanField(default=False)
    profile_completion_percentage = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.user.email


class CustomerAddress(PublicIdMixin, TimeStampedModel):
    class AddressType(models.TextChoices):
        PRESENT = 'present', 'Present'
        PERMANENT = 'permanent', 'Permanent'

    customer_profile = models.ForeignKey(
        CustomerProfile, on_delete=models.CASCADE, related_name='addresses'
    )
    address_type = models.CharField(max_length=20, choices=AddressType.choices)
    full_address = models.TextField()
    city = models.CharField(max_length=100, default='Dhaka', blank=True)
    area = models.CharField(max_length=100, blank=True)
    building_name = models.CharField(max_length=255, blank=True)
    floor = models.CharField(max_length=50, blank=True)
    flat_number = models.CharField(max_length=50, blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_default_delivery = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = 'Customer addresses'

    def __str__(self):
        return f'{self.customer_profile.user.email} - {self.address_type}'


class RiderProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rider_profile')
    vehicle_type = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    is_available = models.BooleanField(default=True)
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)


class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=20, blank=True)
    outlet_id = models.IntegerField(null=True, blank=True)


class AdminProfile(TimeStampedModel):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.user.email


class DeviceToken(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='device_tokens')
    token = models.CharField(max_length=255)
    platform = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
