## ADDED Requirements

### Requirement: Environment-driven AWS credentials with no hardcoded secrets
The system MUST read AWS S3 configuration exclusively from environment variables (via the existing `python-decouple` / `.env` pattern). Source code and committed examples MUST NOT contain real AWS access keys or secret keys.

#### Scenario: Settings load AWS values from environment
- **WHEN** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_S3_CUSTOM_DOMAIN`, and `USE_S3_MEDIA` are set in the environment or `.env`
- **THEN** Django settings MUST expose those values without embedding secrets in Python source

#### Scenario: Empty credentials allowed when S3 disabled
- **WHEN** `USE_S3_MEDIA` is false or unset
- **THEN** the application MUST boot successfully even if AWS access key fields are empty

### Requirement: Toggleable S3 media vs local filesystem storage
When `USE_S3_MEDIA` is true, the Django default file storage MUST use an S3 backend for user-uploaded media. When false, the system MUST use the existing local `MEDIA_ROOT` filesystem storage.

#### Scenario: S3 media enabled
- **WHEN** `USE_S3_MEDIA=True` and required bucket/region settings are present
- **THEN** `STORAGES["default"]` MUST use `core.storage.S3MediaStorage` (or equivalent django-storages S3 backend) so new uploads go to the configured bucket

#### Scenario: S3 media disabled
- **WHEN** `USE_S3_MEDIA` is false or unset
- **THEN** default media storage MUST remain local filesystem under `MEDIA_ROOT` and existing local upload behavior MUST continue to work

#### Scenario: Missing bucket or region when S3 enabled
- **WHEN** `USE_S3_MEDIA=True` but `AWS_STORAGE_BUCKET_NAME` or `AWS_S3_REGION_NAME` is empty
- **THEN** settings load MUST fail with a clear configuration error before serving traffic

### Requirement: Static files remain separate from media storage
Static assets MUST NOT be stored on the S3 media backend. Production static serving MUST continue via WhiteNoise (or the project's existing staticfiles backend); local static MUST remain Django's default staticfiles storage.

#### Scenario: Production static backend unchanged by media S3
- **WHEN** S3 media storage is enabled in production
- **THEN** `STORAGES["staticfiles"]` MUST still use WhiteNoise (or the pre-existing non-S3 static backend), not the media S3 backend

#### Scenario: Local S3 media keeps filesystem static
- **WHEN** local settings enable S3 for media only
- **THEN** staticfiles MUST continue using filesystem static storage

### Requirement: Existing upload paths and APIs stay compatible
Enabling S3 MUST preserve existing ImageField/FileField `upload_to` object key paths. Models, migrations, and API serializers MUST NOT require changes solely for this storage switch. Media field URLs MAY become absolute HTTPS S3 or custom-domain URLs when S3 is enabled.

#### Scenario: Upload path preserved on S3
- **WHEN** a file is saved with an existing `upload_to` path (e.g. meal thumbnails)
- **THEN** the S3 object key MUST match that relative path structure

#### Scenario: No model or API schema migration required
- **WHEN** this change is applied
- **THEN** no database migration and no API request/response field rename or removal MUST be required for storage alone

### Requirement: Optional custom domain for media URLs
When `AWS_S3_CUSTOM_DOMAIN` is set and S3 media is enabled, generated media URLs MUST use that domain. When unset, URLs MUST use the standard S3 HTTPS endpoint for the bucket and region.

#### Scenario: Custom domain configured
- **WHEN** `USE_S3_MEDIA=True` and `AWS_S3_CUSTOM_DOMAIN` is a non-empty host
- **THEN** stored file `.url` values MUST be served under that custom domain

#### Scenario: No custom domain
- **WHEN** `USE_S3_MEDIA=True` and `AWS_S3_CUSTOM_DOMAIN` is empty
- **THEN** file `.url` values MUST still be absolute HTTPS URLs pointing at the S3 bucket

### Requirement: Existing local media can be migrated to S3 safely
The system MUST provide (or retain) a management command that uploads files from local `MEDIA_ROOT` to S3 while preserving relative paths, skipping objects that already exist, and supporting a dry-run mode.

#### Scenario: Dry-run lists uploads without writing
- **WHEN** an operator runs the media migration command with `--dry-run`
- **THEN** the command MUST list files that would be uploaded and MUST NOT upload to S3

#### Scenario: Re-run skips existing objects
- **WHEN** the migration command runs against files already present in the bucket
- **THEN** those objects MUST be skipped without overwrite
