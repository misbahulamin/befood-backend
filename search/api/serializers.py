from rest_framework import serializers

from search.models import SearchDocument, SearchKeyword


DEEP_LINK_HINTS = {
    SearchDocument.DocumentType.PACKAGE: 'package_detail',
    SearchDocument.DocumentType.INSTANT_MEAL: 'instant_meal_detail',
    SearchDocument.DocumentType.FOOD: 'food_detail',
    SearchDocument.DocumentType.CATEGORY: 'category_browse',
}


class SearchResultCardSerializer(serializers.Serializer):
    type = serializers.CharField()
    public_id = serializers.UUIDField()
    name = serializers.CharField()
    name_en = serializers.CharField(allow_blank=True)
    short_description = serializers.CharField(allow_blank=True, required=False)
    image_url = serializers.CharField(allow_blank=True, required=False)
    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        required=False,
    )
    currency = serializers.CharField(required=False)
    is_available = serializers.BooleanField(required=False)
    deep_link_hint = serializers.CharField(required=False)


class SuggestionCardSerializer(serializers.Serializer):
    type = serializers.CharField()
    public_id = serializers.UUIDField()
    name = serializers.CharField()
    name_en = serializers.CharField(allow_blank=True)


class SearchResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    query_normalized = serializers.CharField()
    results = SearchResultCardSerializer(many=True)
    did_you_mean = serializers.CharField(allow_null=True, required=False)
    related = SearchResultCardSerializer(many=True, required=False)


class SuggestionResponseSerializer(serializers.Serializer):
    query = serializers.CharField()
    query_normalized = serializers.CharField()
    results = SuggestionCardSerializer(many=True)


class PopularTermSerializer(serializers.Serializer):
    term = serializers.CharField()
    term_normalized = serializers.CharField()
    source = serializers.CharField()
    count = serializers.IntegerField(allow_null=True)


class PopularResponseSerializer(serializers.Serializer):
    results = PopularTermSerializer(many=True)


class SearchClickSerializer(serializers.Serializer):
    public_id = serializers.UUIDField()
    query = serializers.CharField(required=False, allow_blank=True, default='')
    position = serializers.IntegerField(required=False, allow_null=True, min_value=0)
    session_id = serializers.CharField(required=False, allow_blank=True, default='')


class SearchKeywordSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchKeyword
        fields = (
            'public_id',
            'keyword',
            'keyword_raw',
            'locale_hint',
            'created_at',
        )
        read_only_fields = fields


class SearchKeywordWriteSerializer(serializers.Serializer):
    keyword_raw = serializers.CharField(max_length=255)
    locale_hint = serializers.ChoiceField(
        choices=SearchKeyword.LocaleHint.choices,
        required=False,
        default=SearchKeyword.LocaleHint.OTHER,
    )


class SearchDocumentAdminSerializer(serializers.ModelSerializer):
    keywords = SearchKeywordSerializer(many=True, read_only=True)

    class Meta:
        model = SearchDocument
        fields = (
            'public_id',
            'document_type',
            'title_en',
            'title_bn',
            'short_description',
            'image_url',
            'price',
            'currency',
            'is_active',
            'is_available',
            'popularity_score',
            'category_key',
            'meal_category',
            'ingredient',
            'keywords',
            'created_at',
            'updated_at',
        )
        read_only_fields = ('public_id', 'created_at', 'updated_at', 'keywords')


class SearchDocumentWriteSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(choices=SearchDocument.DocumentType.choices)
    title_en = serializers.CharField(max_length=255)
    title_bn = serializers.CharField(max_length=255, required=False, allow_blank=True, default='')
    short_description = serializers.CharField(required=False, allow_blank=True, default='')
    image_url = serializers.CharField(required=False, allow_blank=True, default='')
    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    currency = serializers.CharField(required=False, default='BDT', max_length=3)
    is_active = serializers.BooleanField(required=False, default=True)
    is_available = serializers.BooleanField(required=False, default=True)
    popularity_score = serializers.IntegerField(required=False, default=0, min_value=0)
    category_key = serializers.CharField(required=False, allow_blank=True, default='')
    keywords = SearchKeywordWriteSerializer(many=True, required=False)


class SearchDocumentUpdateSerializer(serializers.Serializer):
    document_type = serializers.ChoiceField(
        choices=SearchDocument.DocumentType.choices,
        required=False,
    )
    title_en = serializers.CharField(max_length=255, required=False)
    title_bn = serializers.CharField(max_length=255, required=False, allow_blank=True)
    short_description = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.CharField(required=False, allow_blank=True)
    price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    currency = serializers.CharField(required=False, max_length=3)
    is_active = serializers.BooleanField(required=False)
    is_available = serializers.BooleanField(required=False)
    popularity_score = serializers.IntegerField(required=False, min_value=0)
    category_key = serializers.CharField(required=False, allow_blank=True)


class AnalyticsSummarySerializer(serializers.Serializer):
    top_queries = serializers.ListField(child=serializers.DictField())
    zero_result_queries = serializers.ListField(child=serializers.DictField())
    top_clicked = serializers.ListField(child=serializers.DictField())


def document_to_card(document: SearchDocument, *, lean: bool = False) -> dict:
    name = document.title_bn or document.title_en
    payload = {
        'type': document.document_type,
        'public_id': document.public_id,
        'name': name,
        'name_en': document.title_en,
    }
    if lean:
        return payload
    payload.update(
        {
            'short_description': document.short_description or '',
            'image_url': document.image_url or '',
            'price': document.price,
            'currency': document.currency or 'BDT',
            'is_available': document.is_available,
            'deep_link_hint': DEEP_LINK_HINTS.get(document.document_type, 'search_result'),
        }
    )
    return payload


def normalize_session_id(raw: str | None) -> str:
    return (raw or '').strip()[:64]
