from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

from core.models import PublicIdMixin

from blogs.utils.cover_image import blog_cover_upload_path


class BlogCategory(PublicIdMixin, models.Model):
    """Category used to group blog articles and power related suggestions."""

    name = models.CharField(max_length=150, unique=True)
    slug = models.SlugField(max_length=160, unique=True)
    sort_order = models.IntegerField(
        default=0,
        help_text='Lower values appear first in admin filters.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'created_at', 'id']
        verbose_name = 'blog category'
        verbose_name_plural = 'blog categories'
        indexes = [
            models.Index(fields=['is_active', 'sort_order']),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        errors = {}
        name = (self.name or '').strip()
        if not name:
            errors['name'] = 'Name is required.'
        else:
            self.name = name
        slug = (self.slug or '').strip()
        if not slug and name:
            slug = slugify(name)
        if not slug:
            errors['slug'] = 'Slug is required.'
        else:
            self.slug = slug
        if errors:
            raise ValidationError(errors)


class BlogArticle(PublicIdMixin, models.Model):
    """Long-form blog article managed by verified admins."""

    category = models.ForeignKey(
        BlogCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='articles',
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='blog_articles',
    )
    title = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    excerpt = models.TextField(blank=True)
    content = models.TextField()
    cover_image = models.ImageField(
        upload_to=blog_cover_upload_path,
        blank=True,
        null=True,
    )
    cover_image_title = models.CharField(max_length=255, blank=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-published_at', '-id']
        verbose_name = 'blog article'
        verbose_name_plural = 'blog articles'
        indexes = [
            models.Index(fields=['is_published', 'published_at']),
            models.Index(fields=['is_published', 'view_count']),
            models.Index(fields=['category', 'is_published']),
        ]

    def __str__(self):
        return self.title or str(self.public_id)

    def clean(self):
        errors = {}
        title = (self.title or '').strip()
        if not title:
            errors['title'] = 'Title is required.'
        else:
            self.title = title

        content = (self.content or '').strip()
        if not content:
            errors['content'] = 'Content is required.'
        else:
            self.content = content

        slug = (self.slug or '').strip()
        if not slug and title:
            slug = slugify(title)
        if not slug:
            errors['slug'] = 'Slug is required.'
        else:
            self.slug = slug

        if self.is_published and not self.cover_image:
            errors['cover_image'] = 'Cover image is required when publishing.'

        if errors:
            raise ValidationError(errors)
