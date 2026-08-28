import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError
from django.core.exceptions import ImproperlyConfigured
from django.core.files.storage import FileSystemStorage
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from core.settings.aws_media import (
    LOCAL_S3_STORAGES,
    PROD_STORAGES,
    build_s3_media_url,
    validate_aws_media_settings,
)
from core.storage import S3MediaStorage


class S3MediaStorageTests(SimpleTestCase):
    def test_storage_defaults(self):
        storage = S3MediaStorage()
        self.assertIsNone(storage.default_acl)
        self.assertFalse(storage.file_overwrite)
        self.assertFalse(storage.querystring_auth)


class AwsMediaSettingsTests(SimpleTestCase):
    def test_validate_aws_media_settings_requires_bucket_and_region(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            validate_aws_media_settings(bucket_name='', region_name='')
        self.assertIn('AWS_STORAGE_BUCKET_NAME', str(ctx.exception))
        self.assertIn('AWS_S3_REGION_NAME', str(ctx.exception))

    def test_validate_aws_media_settings_passes_with_values(self):
        validate_aws_media_settings(
            bucket_name='test-bucket',
            region_name='ap-south-1',
        )

    def test_prod_storages_use_s3_for_media(self):
        self.assertEqual(
            PROD_STORAGES['default']['BACKEND'],
            'core.storage.S3MediaStorage',
        )
        self.assertIn(
            'whitenoise',
            PROD_STORAGES['staticfiles']['BACKEND'],
        )

    def test_local_s3_storages_use_filesystem_static(self):
        self.assertEqual(
            LOCAL_S3_STORAGES['default']['BACKEND'],
            'core.storage.S3MediaStorage',
        )
        self.assertEqual(
            LOCAL_S3_STORAGES['staticfiles']['BACKEND'],
            'django.contrib.staticfiles.storage.StaticFilesStorage',
        )

    def test_build_s3_media_url_uses_custom_domain(self):
        self.assertEqual(
            build_s3_media_url(
                bucket_name='test-bucket',
                region_name='ap-south-1',
                custom_domain='cdn.example.com',
            ),
            'https://cdn.example.com/',
        )

    def test_build_s3_media_url_accepts_full_custom_domain_url(self):
        self.assertEqual(
            build_s3_media_url(
                bucket_name='test-bucket',
                region_name='ap-south-1',
                custom_domain='https://cdn.example.com',
            ),
            'https://cdn.example.com/',
        )

    def test_build_s3_media_url_uses_bucket_endpoint_without_custom_domain(self):
        self.assertEqual(
            build_s3_media_url(
                bucket_name='befood-production-media',
                region_name='ap-south-1',
                custom_domain='',
            ),
            'https://befood-production-media.s3.ap-south-1.amazonaws.com/',
        )


class LocalFilesystemStorageTests(TestCase):
    def test_default_local_storage_is_filesystem_when_s3_disabled(self):
        from django.conf import settings
        from django.core.files.storage import default_storage

        if settings.USE_S3_MEDIA:
            self.skipTest('USE_S3_MEDIA is enabled in the current environment')
        self.assertIsInstance(default_storage, FileSystemStorage)


class MigrateMediaToS3CommandTests(TestCase):
    def setUp(self):
        self.temp_media = tempfile.TemporaryDirectory()
        self.media_root = Path(self.temp_media.name)
        (self.media_root / 'avatars').mkdir()
        (self.media_root / 'avatars' / 'test.jpg').write_bytes(b'fake-image')

    def tearDown(self):
        self.temp_media.cleanup()

    @override_settings(
        MEDIA_ROOT=tempfile.gettempdir(),
        AWS_STORAGE_BUCKET_NAME='test-bucket',
        AWS_S3_REGION_NAME='ap-south-1',
        AWS_ACCESS_KEY_ID='key',
        AWS_SECRET_ACCESS_KEY='secret',
    )
    @patch('core.management.commands.migrate_media_to_s3.boto3.client')
    def test_dry_run_uploads_nothing(self, mock_boto_client):
        with tempfile.TemporaryDirectory() as media_dir:
            media_path = Path(media_dir)
            (media_path / 'meals').mkdir()
            (media_path / 'meals' / 'thumb.jpg').write_bytes(b'img')

            mock_client = MagicMock()
            mock_client.head_object.side_effect = ClientError(
                {'Error': {'Code': '404', 'Message': 'Not Found'}},
                'HeadObject',
            )
            mock_boto_client.return_value = mock_client

            with override_settings(MEDIA_ROOT=media_dir):
                out = StringIO()
                call_command('migrate_media_to_s3', '--dry-run', stdout=out)

            mock_client.upload_file.assert_not_called()
            self.assertIn('DRY-RUN upload: meals/thumb.jpg', out.getvalue())
            self.assertIn('uploaded=1', out.getvalue())

    @override_settings(
        AWS_STORAGE_BUCKET_NAME='test-bucket',
        AWS_S3_REGION_NAME='ap-south-1',
        AWS_ACCESS_KEY_ID='key',
        AWS_SECRET_ACCESS_KEY='secret',
    )
    @patch('core.management.commands.migrate_media_to_s3.boto3.client')
    def test_skips_existing_s3_objects(self, mock_boto_client):
        mock_client = MagicMock()
        mock_client.head_object.return_value = {'ContentLength': 10}
        mock_boto_client.return_value = mock_client

        with override_settings(MEDIA_ROOT=str(self.media_root)):
            out = StringIO()
            call_command('migrate_media_to_s3', stdout=out)

        mock_client.upload_file.assert_not_called()
        self.assertIn('SKIP (exists): avatars/test.jpg', out.getvalue())
        self.assertIn('skipped=1', out.getvalue())

    @override_settings(
        AWS_STORAGE_BUCKET_NAME='',
        AWS_S3_REGION_NAME='',
    )
    def test_missing_bucket_configuration_raises(self):
        with override_settings(MEDIA_ROOT=str(self.media_root)):
            with self.assertRaises(CommandError):
                call_command('migrate_media_to_s3')
