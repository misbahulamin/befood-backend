import mimetypes
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Upload existing local MEDIA_ROOT files to S3, preserving folder structure.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List files that would be uploaded without uploading.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        media_root = Path(settings.MEDIA_ROOT)

        if not media_root.exists():
            self.stdout.write(
                self.style.WARNING(f'MEDIA_ROOT does not exist: {media_root}')
            )
            return

        bucket = settings.AWS_STORAGE_BUCKET_NAME
        region = settings.AWS_S3_REGION_NAME
        if not bucket or not region:
            raise CommandError(
                'AWS_STORAGE_BUCKET_NAME and AWS_S3_REGION_NAME must be set.'
            )

        client_kwargs = {'region_name': region}
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            client_kwargs['aws_access_key_id'] = settings.AWS_ACCESS_KEY_ID
            client_kwargs['aws_secret_access_key'] = settings.AWS_SECRET_ACCESS_KEY

        s3_client = boto3.client('s3', **client_kwargs)

        uploaded = 0
        skipped = 0
        failed = 0

        for file_path in sorted(media_root.rglob('*')):
            if not file_path.is_file():
                continue

            key = file_path.relative_to(media_root).as_posix()

            if self._object_exists(s3_client, bucket, key):
                self.stdout.write(f'SKIP (exists): {key}')
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f'DRY-RUN upload: {key}')
                uploaded += 1
                continue

            try:
                extra_args = {}
                content_type = mimetypes.guess_type(file_path.name)[0]
                if content_type:
                    extra_args['ContentType'] = content_type
                if extra_args:
                    s3_client.upload_file(
                        str(file_path),
                        bucket,
                        key,
                        ExtraArgs=extra_args,
                    )
                else:
                    s3_client.upload_file(str(file_path), bucket, key)
                self.stdout.write(self.style.SUCCESS(f'UPLOADED: {key}'))
                uploaded += 1
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'FAILED: {key} — {exc}'))
                failed += 1

        self.stdout.write('')
        self.stdout.write(
            f'Summary: uploaded={uploaded}, skipped={skipped}, failed={failed}'
        )

        if failed:
            raise CommandError(f'{failed} file(s) failed to upload.')

    def _object_exists(self, s3_client, bucket, key):
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as exc:
            error_code = exc.response.get('Error', {}).get('Code', '')
            if error_code in ('404', 'NoSuchKey', 'NotFound'):
                return False
            raise
