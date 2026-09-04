from rest_framework import serializers

from support.models import SupportConversation, SupportMessage
from support.services.presence import customer_online_for_conversation, support_agent_online


class SupportMessageSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = SupportMessage
        fields = (
            'public_id',
            'sender_type',
            'body',
            'is_read_by_customer',
            'is_read_by_admin',
            'created_at',
        )
        read_only_fields = fields


class SupportMessageCreateSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=False)
    body = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        text = attrs.get('message') or attrs.get('body') or ''
        text = text.strip()
        if not text:
            raise serializers.ValidationError({'message': ['This field is required.']})
        attrs['message'] = text
        return attrs


class CustomerConversationSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(read_only=True)
    support_agent_online = serializers.SerializerMethodField()

    class Meta:
        model = SupportConversation
        fields = (
            'public_id',
            'status',
            'last_message',
            'last_message_at',
            'customer_unread_count',
            'created_at',
            'updated_at',
            'support_agent_online',
        )
        read_only_fields = fields

    def get_support_agent_online(self, obj) -> bool:
        return support_agent_online()


class AdminConversationListSerializer(serializers.ModelSerializer):
    public_id = serializers.UUIDField(read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_phone = serializers.SerializerMethodField()
    customer_email = serializers.SerializerMethodField()
    customer_public_id = serializers.SerializerMethodField()
    customer_online = serializers.SerializerMethodField()

    class Meta:
        model = SupportConversation
        fields = (
            'public_id',
            'status',
            'last_message',
            'last_message_at',
            'admin_unread_count',
            'customer_unread_count',
            'customer_public_id',
            'customer_name',
            'customer_phone',
            'customer_email',
            'customer_online',
            'created_at',
            'updated_at',
        )
        read_only_fields = fields

    def get_customer_name(self, obj) -> str:
        user = obj.customer.user
        return (user.get_full_name() or user.username or '').strip()

    def get_customer_phone(self, obj) -> str:
        return obj.customer.phone or ''

    def get_customer_email(self, obj) -> str:
        return obj.customer.user.email or ''

    def get_customer_public_id(self, obj) -> str:
        return str(obj.customer.public_id)

    def get_customer_online(self, obj) -> bool:
        return customer_online_for_conversation(str(obj.public_id))


class AdminConversationDetailSerializer(AdminConversationListSerializer):
    pass


class AdminReplySerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=False)
    body = serializers.CharField(required=False, allow_blank=False)

    def validate(self, attrs):
        text = attrs.get('message') or attrs.get('body') or ''
        text = text.strip()
        if not text:
            raise serializers.ValidationError({'message': ['This field is required.']})
        attrs['message'] = text
        return attrs


class AdminStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SupportConversation.Status.choices)
