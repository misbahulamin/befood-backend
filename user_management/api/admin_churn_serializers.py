from rest_framework import serializers

from orders.models import ChurnFollowUp


class ChurnFollowUpSerializer(serializers.ModelSerializer):
    customer_public_id = serializers.UUIDField(source='customer.public_id', read_only=True)
    admin_email = serializers.EmailField(source='admin.email', read_only=True, allow_null=True)

    class Meta:
        model = ChurnFollowUp
        fields = (
            'public_id',
            'customer_public_id',
            'status',
            'note',
            'admin_email',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields


class ChurnFollowUpCreateSerializer(serializers.Serializer):
    customer_public_id = serializers.UUIDField()
    status = serializers.ChoiceField(choices=ChurnFollowUp.Status.choices)
    note = serializers.CharField(required=False, allow_blank=True, default='')


class ChurnFollowUpUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=ChurnFollowUp.Status.choices,
        required=False,
    )
    note = serializers.CharField(required=False, allow_blank=True)
