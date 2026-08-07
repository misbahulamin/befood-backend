from rest_framework import serializers

from onahar.models import (
    OnaharAuditLog,
    OnaharContribution,
    OnaharDistribution,
    OnaharDistributionMedia,
    OnaharFundLedgerEntry,
    OnaharMonthlyProgress,
    OnaharPrivacyPreference,
    OnaharTargetHistory,
)


class OnaharStatsSerializer(serializers.Serializer):
    total_meals_contributed = serializers.IntegerField()
    total_meals_distributed = serializers.IntegerField()
    available_meals = serializers.IntegerField()
    total_contributors = serializers.IntegerField()
    total_distribution_campaigns = serializers.IntegerField()
    current_month_contributions = serializers.IntegerField()
    current_contribution_target = serializers.IntegerField()


class LeaderboardEntrySerializer(serializers.Serializer):
    rank = serializers.IntegerField()
    display_name = serializers.CharField()
    total_meals = serializers.IntegerField()


class PublicLedgerEntrySerializer(serializers.Serializer):
    entry_side = serializers.ChoiceField(choices=['contribution', 'distribution'])
    occurred_at = serializers.DateTimeField()
    meals = serializers.IntegerField()
    display_name = serializers.CharField(required=False, allow_null=True)
    location = serializers.CharField(required=False, allow_null=True)
    campaign_public_id = serializers.UUIDField(required=False, allow_null=True)
    campaign_title = serializers.CharField(required=False, allow_null=True)


class DistributionMediaSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = OnaharDistributionMedia
        fields = ('public_id', 'image_url', 'caption', 'sort_order')

    def get_image_url(self, obj):
        request = self.context.get('request')
        if not obj.image:
            return None
        url = obj.image.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class PublicDistributionListSerializer(serializers.ModelSerializer):
    cover_image_url = serializers.SerializerMethodField()

    class Meta:
        model = OnaharDistribution
        fields = (
            'public_id',
            'title',
            'location',
            'distribution_date',
            'meals_distributed',
            'description',
            'cover_image_url',
            'published_at',
        )

    def get_cover_image_url(self, obj):
        media = obj.media.order_by('sort_order', 'id').first()
        if not media or not media.image:
            return None
        request = self.context.get('request')
        url = media.image.url
        if request is not None:
            return request.build_absolute_uri(url)
        return url


class PublicDistributionDetailSerializer(serializers.ModelSerializer):
    media = DistributionMediaSerializer(many=True, read_only=True)

    class Meta:
        model = OnaharDistribution
        fields = (
            'public_id',
            'title',
            'location',
            'full_address',
            'distribution_date',
            'meals_distributed',
            'description',
            'beneficiary_info',
            'published_at',
            'media',
        )


class CustomerProgressSerializer(serializers.Serializer):
    year_month = serializers.CharField()
    current_points = serializers.IntegerField()
    target = serializers.IntegerField()
    contributions_earned = serializers.IntegerField()
    remaining_points = serializers.IntegerField()
    points_to_next_contribution = serializers.IntegerField()
    status = serializers.CharField()
    total_eligible_meals = serializers.IntegerField()
    total_onahar_meals_contributed = serializers.IntegerField()
    current_ranking = serializers.IntegerField(allow_null=True)


class CustomerHistorySerializer(serializers.ModelSerializer):
    remaining_or_expired_points = serializers.SerializerMethodField()

    class Meta:
        model = OnaharMonthlyProgress
        fields = (
            'year_month',
            'net_points',
            'target_snapshot',
            'contributions_earned',
            'expired_points',
            'remaining_or_expired_points',
            'status',
            'closed_at',
            'created_at',
            'updated_at',
        )

    def get_remaining_or_expired_points(self, obj):
        if obj.status == OnaharMonthlyProgress.Status.CLOSED:
            return obj.expired_points
        return obj.remaining_points


class PrivacySerializer(serializers.ModelSerializer):
    class Meta:
        model = OnaharPrivacyPreference
        fields = ('display_mode', 'updated_at')
        read_only_fields = ('updated_at',)


class PrivacyUpdateSerializer(serializers.Serializer):
    display_mode = serializers.ChoiceField(choices=OnaharPrivacyPreference.DisplayMode.choices)


class SettingsSerializer(serializers.Serializer):
    contribution_target = serializers.IntegerField(min_value=1)
    total_contributed_meals = serializers.IntegerField(read_only=True)
    total_distributed_meals = serializers.IntegerField(read_only=True)
    available_meals = serializers.IntegerField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)


class SettingsUpdateSerializer(serializers.Serializer):
    contribution_target = serializers.IntegerField(min_value=1)


class TargetHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.SerializerMethodField()

    class Meta:
        model = OnaharTargetHistory
        fields = (
            'previous_target',
            'new_target',
            'changed_by_username',
            'created_at',
        )

    def get_changed_by_username(self, obj):
        if obj.changed_by_id is None:
            return None
        return obj.changed_by.username


class AdminDistributionSerializer(serializers.ModelSerializer):
    media = DistributionMediaSerializer(many=True, read_only=True)

    class Meta:
        model = OnaharDistribution
        fields = (
            'public_id',
            'title',
            'location',
            'full_address',
            'distribution_date',
            'meals_distributed',
            'description',
            'beneficiary_info',
            'status',
            'published_at',
            'cancelled_at',
            'created_at',
            'updated_at',
            'media',
        )
        read_only_fields = (
            'public_id',
            'status',
            'published_at',
            'cancelled_at',
            'created_at',
            'updated_at',
            'media',
        )


class AdminDistributionWriteSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255)
    location = serializers.CharField(max_length=255)
    full_address = serializers.CharField(required=False, allow_blank=True, default='')
    distribution_date = serializers.DateField()
    meals_distributed = serializers.IntegerField(min_value=1)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    beneficiary_info = serializers.CharField(required=False, allow_blank=True, default='')


class AdminDistributionUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    location = serializers.CharField(max_length=255, required=False)
    full_address = serializers.CharField(required=False, allow_blank=True)
    distribution_date = serializers.DateField(required=False)
    meals_distributed = serializers.IntegerField(min_value=1, required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    beneficiary_info = serializers.CharField(required=False, allow_blank=True)


class FundSummarySerializer(serializers.Serializer):
    total_contributed_meals = serializers.IntegerField()
    total_distributed_meals = serializers.IntegerField()
    available_meals = serializers.IntegerField()
    contribution_target = serializers.IntegerField()


class AuditLogSerializer(serializers.ModelSerializer):
    actor_username = serializers.SerializerMethodField()

    class Meta:
        model = OnaharAuditLog
        fields = (
            'id',
            'action',
            'actor_username',
            'previous_value',
            'new_value',
            'metadata',
            'created_at',
        )

    def get_actor_username(self, obj):
        if obj.actor_id is None:
            return None
        return obj.actor.username
