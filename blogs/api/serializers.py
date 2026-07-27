from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.text import slugify
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from blogs.models import BlogArticle, BlogCategory
from blogs.services import apply_publish_state
from blogs.utils.cover_image import validate_image_extension, validate_image_size


def _raise_drf(exc: DjangoValidationError) -> None:
    if hasattr(exc, 'message_dict'):
        raise serializers.ValidationError(exc.message_dict) from exc
    raise serializers.ValidationError({'detail': list(exc.messages)}) from exc


def _author_display_name(user) -> str:
    if user is None:
        return ''
    full = (user.get_full_name() or '').strip()
    if full:
        return full
    return user.username or user.email or ''


def _absolute_cover_url(obj, request):
    if not obj.cover_image:
        return None
    url = obj.cover_image.url
    return request.build_absolute_uri(url) if request else url


def _unique_slug(model, base_slug: str, *, exclude_pk=None) -> str:
    slug = base_slug or 'item'
    candidate = slug
    counter = 2
    while True:
        qs = model.objects.filter(slug=candidate)
        if exclude_pk is not None:
            qs = qs.exclude(pk=exclude_pk)
        if not qs.exists():
            return candidate
        candidate = f'{slug}-{counter}'
        counter += 1


class BlogCategoryAdminSerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = (
            'public_id',
            'name',
            'slug',
            'sort_order',
            'is_active',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'public_id',
            'created_at',
            'updated_at',
        )
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True},
        }

    def validate_name(self, value):
        name = (value or '').strip()
        if not name:
            raise serializers.ValidationError('Name is required.')
        qs = BlogCategory.objects.filter(name__iexact=name)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'A blog category with this name already exists.'
            )
        return name

    def validate_slug(self, value):
        slug = (value or '').strip()
        if not slug:
            return slug
        qs = BlogCategory.objects.filter(slug=slug)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'A blog category with this slug already exists.'
            )
        return slug

    def create(self, validated_data):
        name = validated_data['name']
        slug = (validated_data.get('slug') or '').strip()
        if not slug:
            slug = _unique_slug(BlogCategory, slugify(name))
        validated_data['slug'] = slug
        instance = BlogCategory(**validated_data)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        if 'name' in validated_data and 'slug' not in validated_data:
            # Keep existing slug unless client sends a new one.
            pass
        if 'slug' in validated_data:
            slug = (validated_data.get('slug') or '').strip()
            if not slug:
                name = validated_data.get('name', instance.name)
                validated_data['slug'] = _unique_slug(
                    BlogCategory,
                    slugify(name),
                    exclude_pk=instance.pk,
                )
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance


class NestedBlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = BlogCategory
        fields = ('public_id', 'name')
        read_only_fields = fields


class BlogArticleAdminSerializer(serializers.ModelSerializer):
    category_public_id = serializers.UUIDField(
        required=False,
        allow_null=True,
        write_only=True,
    )
    cover_image = serializers.ImageField(required=False, allow_null=True)
    author_display_name = serializers.SerializerMethodField()
    author_username = serializers.SerializerMethodField()
    category = NestedBlogCategorySerializer(read_only=True)

    class Meta:
        model = BlogArticle
        fields = (
            'public_id',
            'category',
            'category_public_id',
            'title',
            'slug',
            'excerpt',
            'content',
            'cover_image',
            'cover_image_title',
            'is_published',
            'published_at',
            'view_count',
            'author_display_name',
            'author_username',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'public_id',
            'published_at',
            'view_count',
            'author_display_name',
            'author_username',
            'created_at',
            'updated_at',
        )
        extra_kwargs = {
            'slug': {'required': False, 'allow_blank': True},
            'excerpt': {'required': False, 'allow_blank': True},
            'cover_image_title': {'required': False, 'allow_blank': True},
        }

    @extend_schema_field(serializers.CharField())
    def get_author_display_name(self, obj):
        return _author_display_name(obj.author)

    @extend_schema_field(serializers.CharField())
    def get_author_username(self, obj):
        return obj.author.username if obj.author_id else ''

    def validate_category_public_id(self, value):
        if value is None:
            return None
        try:
            return BlogCategory.objects.get(public_id=value)
        except BlogCategory.DoesNotExist as exc:
            raise serializers.ValidationError('Blog category not found.') from exc

    def validate_title(self, value):
        title = (value or '').strip()
        if not title:
            raise serializers.ValidationError('Title is required.')
        return title

    def validate_content(self, value):
        content = (value or '').strip()
        if not content:
            raise serializers.ValidationError('Content is required.')
        return content

    def validate_slug(self, value):
        slug = (value or '').strip()
        if not slug:
            return slug
        qs = BlogArticle.objects.filter(slug=slug)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'A blog article with this slug already exists.'
            )
        return slug

    def validate_cover_image(self, value):
        if value is None:
            return value
        try:
            validate_image_extension(value.name)
            validate_image_size(value)
        except ValueError as exc:
            raise serializers.ValidationError(str(exc)) from exc
        return value

    def create(self, validated_data):
        request = self.context.get('request')
        category = validated_data.pop('category_public_id', None)
        title = validated_data['title']
        slug = (validated_data.get('slug') or '').strip()
        if not slug:
            slug = _unique_slug(BlogArticle, slugify(title))
        validated_data['slug'] = slug

        article = BlogArticle(
            author=request.user,
            category=category,
            **validated_data,
        )
        apply_publish_state(article)
        try:
            article.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        article.save()
        return article

    def update(self, instance, validated_data):
        # Ignore any client-supplied author overrides (field not in writable Meta).
        if 'category_public_id' in validated_data:
            instance.category = validated_data.pop('category_public_id')

        if 'slug' in validated_data:
            slug = (validated_data.get('slug') or '').strip()
            if not slug:
                title = validated_data.get('title', instance.title)
                validated_data['slug'] = _unique_slug(
                    BlogArticle,
                    slugify(title),
                    exclude_pk=instance.pk,
                )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        apply_publish_state(instance)
        try:
            instance.full_clean()
        except DjangoValidationError as exc:
            _raise_drf(exc)
        instance.save()
        return instance

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['cover_image'] = _absolute_cover_url(instance, self.context.get('request'))
        if instance.category_id:
            data['category_public_id'] = str(instance.category.public_id)
        else:
            data['category_public_id'] = None
        return data


class PublicBlogArticleCardSerializer(serializers.ModelSerializer):
    cover_image = serializers.SerializerMethodField()
    author_display_name = serializers.SerializerMethodField()
    category = NestedBlogCategorySerializer(read_only=True)

    class Meta:
        model = BlogArticle
        fields = (
            'public_id',
            'title',
            'slug',
            'excerpt',
            'cover_image',
            'cover_image_title',
            'author_display_name',
            'category',
            'published_at',
            'view_count',
        )
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_cover_image(self, obj):
        return _absolute_cover_url(obj, self.context.get('request'))

    @extend_schema_field(serializers.CharField())
    def get_author_display_name(self, obj):
        return _author_display_name(obj.author)


class PublicBlogArticleDetailSerializer(PublicBlogArticleCardSerializer):
    class Meta(PublicBlogArticleCardSerializer.Meta):
        fields = PublicBlogArticleCardSerializer.Meta.fields + ('content',)
        read_only_fields = fields
