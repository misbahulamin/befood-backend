from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from faqs.models import FaqQuestion, FaqType


def _raise_drf(exc: DjangoValidationError) -> None:
    if hasattr(exc, 'message_dict'):
        raise serializers.ValidationError(exc.message_dict) from exc
    raise serializers.ValidationError({'detail': list(exc.messages)}) from exc


class FaqTypeAdminSerializer(serializers.ModelSerializer):
    question_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = FaqType
        fields = (
            'public_id',
            'name',
            'sort_order',
            'is_active',
            'question_count',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'public_id',
            'question_count',
            'created_at',
            'updated_at',
        )

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('Name is required.')
        qs = FaqType.objects.filter(name__iexact=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A FAQ type with this name already exists.')
        return name

    def create(self, validated_data):
        instance = FaqType(**validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'question_count' not in data or data['question_count'] is None:
            data['question_count'] = instance.questions.count()
        return data


class FaqQuestionAdminSerializer(serializers.ModelSerializer):
    type_public_id = serializers.UUIDField(write_only=True)

    class Meta:
        model = FaqQuestion
        fields = (
            'public_id',
            'type_public_id',
            'question',
            'answer',
            'is_published',
            'sort_order',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('public_id', 'created_at', 'updated_at')

    def validate_type_public_id(self, value):
        try:
            return FaqType.objects.get(public_id=value)
        except FaqType.DoesNotExist as exc:
            raise serializers.ValidationError('FAQ type not found.') from exc

    def validate_question(self, value):
        question = (value or '').strip()
        if not question:
            raise serializers.ValidationError('Question is required.')
        return question

    def validate_answer(self, value):
        answer = (value or '').strip()
        if not answer:
            raise serializers.ValidationError('Answer is required.')
        return answer

    def create(self, validated_data):
        faq_type = validated_data.pop('type_public_id')
        instance = FaqQuestion(type=faq_type, **validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        if 'type_public_id' in validated_data:
            instance.type = validated_data.pop('type_public_id')
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['type_public_id'] = str(instance.type.public_id)
        return data


class PublicFaqQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = FaqQuestion
        fields = (
            'public_id',
            'question',
            'answer',
            'sort_order',
        )
        read_only_fields = fields


class PublicFaqTypeSerializer(serializers.ModelSerializer):
    questions = PublicFaqQuestionSerializer(many=True, read_only=True)

    class Meta:
        model = FaqType
        fields = (
            'public_id',
            'name',
            'sort_order',
            'questions',
        )
        read_only_fields = fields
