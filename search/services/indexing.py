from __future__ import annotations

from django.db import transaction

from meals.models import Ingredient, MealCategory
from search.models import SearchDocument, SearchKeyword
from search.services.catalog_cache import invalidate_catalog_cache
from search.services.normalize import normalize_query

CATEGORY_FACETS = [
    {
        'category_key': 'monthly_package',
        'title_en': 'Monthly Package',
        'title_bn': 'মাসিক প্যাকেজ',
        'keywords': ['monthly', 'monthly package', 'মাসিক', 'package'],
    },
    {
        'category_key': 'student_package',
        'title_en': 'Student Package',
        'title_bn': 'স্টুডেন্ট প্যাকেজ',
        'keywords': ['student', 'student package', 'স্টুডেন্ট'],
    },
    {
        'category_key': 'regular_package',
        'title_en': 'Regular Package',
        'title_bn': 'রেগুলার প্যাকেজ',
        'keywords': ['regular', 'regular package', 'রেগুলার'],
    },
    {
        'category_key': 'family_package',
        'title_en': 'Family Package',
        'title_bn': 'ফ্যামিলি প্যাকেজ',
        'keywords': ['family', 'family package', 'ফ্যামিলি'],
    },
    {
        'category_key': 'instant_meal',
        'title_en': 'Instant Meal',
        'title_bn': 'ইনস্ট্যান্ট মিল',
        'keywords': ['instant', 'instant meal', 'daily', 'ইনস্ট্যান্ট'],
    },
]

COMMON_KEYWORD_PACKS: dict[str, list[tuple[str, str]]] = {
    # title_en lower key -> list of (raw_keyword, locale_hint)
    'rice': [
        ('ভাত', 'bn'),
        ('vat', 'banglish'),
        ('bhat', 'banglish'),
        ('rice', 'en'),
    ],
    'chicken': [
        ('চিকেন', 'bn'),
        ('chicken', 'en'),
        ('murgi', 'banglish'),
        ('মুরগি', 'bn'),
    ],
    'kacchi': [
        ('কাচ্চি', 'bn'),
        ('কাচ্চি বিরিয়ানি', 'bn'),
        ('kacchi', 'banglish'),
        ('kachchi', 'banglish'),
        ('kachi', 'banglish'),
        ('kacci', 'banglish'),
        ('biryani', 'en'),
        ('biriani', 'banglish'),
        ('biriyani', 'banglish'),
    ],
    'fish': [
        ('মাছ', 'bn'),
        ('mach', 'banglish'),
        ('maach', 'banglish'),
        ('fish', 'en'),
    ],
    'khichuri': [
        ('খিচুড়ি', 'bn'),
        ('khichuri', 'banglish'),
        ('khichdi', 'banglish'),
        ('kichuri', 'banglish'),
    ],
}


def _meal_document_type(meal: MealCategory) -> str:
    if meal.meal_type == MealCategory.MealType.DAILY:
        return SearchDocument.DocumentType.INSTANT_MEAL
    return SearchDocument.DocumentType.PACKAGE


def _image_url_for_meal(meal: MealCategory) -> str:
    if meal.meal_thumbnail:
        try:
            return meal.meal_thumbnail.url
        except ValueError:
            return ''
    return ''


@transaction.atomic
def sync_search_catalog() -> dict[str, int]:
    """
    Upsert documents from meals/ingredients/category facets.
    Does not delete or wipe curated keywords on existing documents.
    """
    created = 0
    updated = 0

    for meal in MealCategory.objects.filter(is_active=True):
        doc_type = _meal_document_type(meal)
        defaults = {
            'document_type': doc_type,
            'title_en': meal.meal_name,
            'short_description': meal.description or '',
            'image_url': _image_url_for_meal(meal),
            'price': meal.total_price,
            'currency': 'BDT',
            'is_active': True,
            'is_available': meal.total_price is not None,
            'ingredient': None,
            'category_key': '',
        }
        document, was_created = SearchDocument.objects.update_or_create(
            meal_category=meal,
            defaults=defaults,
        )
        created += int(was_created)
        updated += int(not was_created)
        _ensure_title_keywords(document)

    for ingredient in Ingredient.objects.filter(is_active=True, is_customer_visible=True):
        defaults = {
            'document_type': SearchDocument.DocumentType.FOOD,
            'title_en': ingredient.name,
            'short_description': ingredient.notes or '',
            'image_url': '',
            'price': None,
            'is_active': True,
            'is_available': True,
            'meal_category': None,
            'category_key': '',
        }
        document, was_created = SearchDocument.objects.update_or_create(
            ingredient=ingredient,
            defaults=defaults,
        )
        created += int(was_created)
        updated += int(not was_created)
        _ensure_title_keywords(document)
        _apply_common_keyword_pack(document)

    for facet in CATEGORY_FACETS:
        defaults = {
            'document_type': SearchDocument.DocumentType.CATEGORY,
            'title_en': facet['title_en'],
            'title_bn': facet['title_bn'],
            'short_description': '',
            'is_active': True,
            'is_available': True,
            'meal_category': None,
            'ingredient': None,
        }
        document, was_created = SearchDocument.objects.update_or_create(
            category_key=facet['category_key'],
            defaults=defaults,
        )
        created += int(was_created)
        updated += int(not was_created)
        for raw in facet['keywords']:
            add_keyword(document, raw, locale_hint='other', raise_on_duplicate=False)

    invalidate_catalog_cache()
    return {'created': created, 'updated': updated}


def _ensure_title_keywords(document: SearchDocument) -> None:
    for raw, hint in ((document.title_en, 'en'), (document.title_bn, 'bn')):
        if raw:
            add_keyword(document, raw, locale_hint=hint, raise_on_duplicate=False)


def _apply_common_keyword_pack(document: SearchDocument) -> None:
    key = normalize_query(document.title_en)
    pack = COMMON_KEYWORD_PACKS.get(key)
    if not pack:
        # Partial pack match (e.g. "Chicken Curry" contains chicken)
        for pack_key, keywords in COMMON_KEYWORD_PACKS.items():
            if pack_key in key or key in pack_key:
                pack = keywords
                break
    if not pack:
        return
    for raw, locale in pack:
        add_keyword(document, raw, locale_hint=locale, raise_on_duplicate=False)


def add_keyword(
    document: SearchDocument,
    keyword_raw: str,
    *,
    locale_hint: str = 'other',
    raise_on_duplicate: bool = True,
) -> SearchKeyword | None:
    normalized = normalize_query(keyword_raw)
    if not normalized:
        raise ValueError('Keyword is empty after normalization.')
    existing = SearchKeyword.objects.filter(document=document, keyword=normalized).first()
    if existing:
        if raise_on_duplicate:
            raise ValueError('Duplicate keyword for document.')
        return existing
    return SearchKeyword.objects.create(
        document=document,
        keyword=normalized,
        keyword_raw=keyword_raw.strip(),
        locale_hint=locale_hint
        if locale_hint in SearchKeyword.LocaleHint.values
        else SearchKeyword.LocaleHint.OTHER,
    )


def seed_common_keyword_packs() -> int:
    """Attach common synonym packs to matching food documents by title."""
    count = 0
    foods = SearchDocument.objects.filter(
        document_type=SearchDocument.DocumentType.FOOD,
        is_active=True,
    )
    for document in foods:
        before = document.keywords.count()
        _apply_common_keyword_pack(document)
        after = document.keywords.count()
        count += max(0, after - before)

    # Ensure curated kacchi/rice docs exist even without ingredient source.
    for title_en, title_bn, pack_key in (
        ('Rice', 'ভাত', 'rice'),
        ('Kacchi Biryani', 'কাচ্চি বিরিয়ানি', 'kacchi'),
        ('Chicken', 'চিকেন', 'chicken'),
        ('Fish', 'মাছ', 'fish'),
        ('Khichuri', 'খিচুড়ি', 'khichuri'),
    ):
        document = SearchDocument.objects.filter(
            document_type=SearchDocument.DocumentType.FOOD,
            title_en=title_en,
            meal_category__isnull=True,
            ingredient__isnull=True,
        ).first()
        if document is None:
            document = SearchDocument.objects.create(
                document_type=SearchDocument.DocumentType.FOOD,
                title_en=title_en,
                title_bn=title_bn,
                is_active=True,
                is_available=True,
            )
        elif not document.title_bn:
            document.title_bn = title_bn
            document.save(update_fields=['title_bn', 'updated_at'])
        before = document.keywords.count()
        for raw, locale in COMMON_KEYWORD_PACKS.get(pack_key, []):
            add_keyword(document, raw, locale_hint=locale, raise_on_duplicate=False)
        after = document.keywords.count()
        count += max(0, after - before)

    invalidate_catalog_cache()
    return count
