from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from decimal import Decimal

from core.models import PublicIdMixin
from user_management.services.profile_picture import profile_picture_upload_path


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CustomerProfile(PublicIdMixin, TimeStampedModel):
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
    phone = models.CharField(max_length=10, unique=True, null=True, blank=True)
    occupation = models.CharField(max_length=30, choices=Occupation.choices, null=True, blank=True)
    is_bachelor = models.BooleanField(null=True, blank=True)
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

    profile_picture = models.ImageField(
        upload_to=profile_picture_upload_path,
        blank=True,
        null=True,
    )

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


class CustomerDeliveryPlace(PublicIdMixin, TimeStampedModel):
    """Labeled delivery destination (Home, Office, …), separate from present/permanent."""

    class LocationSource(models.TextChoices):
        GPS = 'gps', 'GPS'
        MANUAL = 'manual', 'Manual'
        MAP_PIN = 'map_pin', 'Map pin'
        SEARCH = 'search', 'Search'
        GUEST_MIGRATION = 'guest_migration', 'Guest migration'

    customer_profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='delivery_places',
    )
    label = models.CharField(max_length=100)
    full_address = models.TextField()
    city = models.CharField(max_length=100, default='Dhaka', blank=True)
    area = models.CharField(max_length=100, blank=True)
    building_name = models.CharField(max_length=255, blank=True)
    floor = models.CharField(max_length=50, blank=True)
    flat_number = models.CharField(max_length=50, blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_source = models.CharField(
        max_length=32,
        choices=LocationSource.choices,
        blank=True,
        default='',
        help_text='Blank for legacy places created before location enrichment.',
    )
    location_accuracy = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='GPS accuracy in meters when provided.',
    )
    formatted_address = models.CharField(max_length=512, blank=True, default='')
    is_verified_location = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Customer delivery places'

    def __str__(self):
        return f'{self.customer_profile.user.email} - {self.label}'


class MealDeliveryPreference(TimeStampedModel):
    """Usual lunch/dinner delivery places for a customer (at most one each)."""

    customer_profile = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='meal_delivery_preference',
    )
    lunch_place = models.ForeignKey(
        CustomerDeliveryPlace,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lunch_preference_set',
    )
    dinner_place = models.ForeignKey(
        CustomerDeliveryPlace,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dinner_preference_set',
    )

    def __str__(self):
        return f'Delivery prefs for {self.customer_profile.user.email}'


class MealDeliveryDayOverride(TimeStampedModel):
    """Weekday override: on this weekday, use a different place for lunch or dinner."""

    class MealPeriod(models.TextChoices):
        LUNCH = 'lunch', 'Lunch'
        DINNER = 'dinner', 'Dinner'

    customer_profile = models.ForeignKey(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='meal_delivery_day_overrides',
    )
    meal_period = models.CharField(max_length=10, choices=MealPeriod.choices)
    weekday = models.PositiveSmallIntegerField(
        help_text='ISO weekday: Monday=0 … Sunday=6.',
    )
    place = models.ForeignKey(
        CustomerDeliveryPlace,
        on_delete=models.CASCADE,
        related_name='day_overrides',
    )

    class Meta:
        ordering = ['weekday', 'meal_period']
        constraints = [
            models.UniqueConstraint(
                fields=['customer_profile', 'meal_period', 'weekday'],
                name='unique_meal_delivery_day_override',
            ),
            models.CheckConstraint(
                check=models.Q(weekday__gte=0) & models.Q(weekday__lte=6),
                name='meal_delivery_day_override_weekday_range',
            ),
        ]

    def __str__(self):
        return (
            f'{self.customer_profile.user.email} '
            f'{self.meal_period} weekday={self.weekday} → {self.place.label}'
        )


class CustomerLocationSettings(models.Model):
    """Singleton: duplicate radius, max places, and location refresh interval."""

    duplicate_radius_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal('0.50'),
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Reject new/updated places within this distance (km) of another active place.',
    )
    max_active_delivery_places = models.PositiveSmallIntegerField(
        default=3,
        validators=[MinValueValidator(1)],
        help_text='Maximum active delivery places per customer.',
    )
    location_refresh_interval_hours = models.PositiveIntegerField(
        default=24,
        validators=[MinValueValidator(1)],
        help_text='Hours after last detection before clients should prompt GPS again.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Customer location settings'
        verbose_name_plural = 'Customer location settings'

    def __str__(self):
        return (
            f'Location settings dupe={self.duplicate_radius_km}km '
            f'max={self.max_active_delivery_places} refresh={self.location_refresh_interval_hours}h'
        )

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls) -> 'CustomerLocationSettings':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CustomerLocationPreference(TimeStampedModel):
    """Per-customer cached saved delivery location vs last-detected GPS."""

    customer_profile = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='location_preference',
    )
    active_delivery_place = models.ForeignKey(
        CustomerDeliveryPlace,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='active_location_preferences',
    )
    saved_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    saved_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    saved_location_name = models.CharField(max_length=255, blank=True, default='')
    saved_at = models.DateTimeField(null=True, blank=True)
    last_detected_latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    last_detected_longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    last_detected_location_name = models.CharField(max_length=255, blank=True, default='')
    last_detected_accuracy = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    detected_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f'Location preference for {self.customer_profile.user.email}'


class RiderProfile(PublicIdMixin, TimeStampedModel):
    """Delivery Man profile (API paths use deliveryman; ORM related_name stays rider_profile)."""

    class ApprovalStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='rider_profile')
    phone = models.CharField(max_length=10, unique=True, null=True, blank=True)
    address = models.TextField(blank=True)
    vehicle_type = models.CharField(max_length=100, blank=True)
    license_number = models.CharField(max_length=100, blank=True)
    is_available = models.BooleanField(default=True)
    current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    approval_status = models.CharField(
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True)

    def __str__(self):
        return self.user.email


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


class CustomerAuthOTP(models.Model):
    """Hashed one-time codes for customer email verification and password reset."""

    class Purpose(models.TextChoices):
        EMAIL_VERIFICATION = 'email_verification', 'Email verification'
        PASSWORD_RESET = 'password_reset', 'Password reset'

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auth_otps')
    purpose = models.CharField(max_length=32, choices=Purpose.choices, db_index=True)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'purpose', '-created_at']),
        ]
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.purpose} OTP for user={self.user_id}'

    @property
    def is_consumed(self):
        return self.consumed_at is not None
