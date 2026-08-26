## ADDED Requirements

### Requirement: Production media stored on AWS S3

When `DJANGO_ENV=prod` and AWS credentials are configured, the system MUST store all `FileField` and `ImageField` uploads in the configured S3 bucket using the existing `upload_to` paths (no model changes).

#### Scenario: New meal thumbnail upload in production

- **WHEN** an admin uploads a meal thumbnail via API or Django admin in production
- **THEN** the file is saved to S3 at `meals/thumbnails/<generated-filename>`
- **AND** `meal_thumbnail.url` returns an HTTPS URL pointing to the S3 bucket (not `/media/...`)

#### Scenario: Existing upload paths preserved

- **WHEN** a file is uploaded for any existing model (`avatars/`, `business/`, `blogs/covers/`, `announcements/banners/`, `promotions/`, `onahar/distributions/`, `inventory/invoices/`)
- **THEN** the S3 object key matches the same relative path that local storage would have used

### Requirement: AWS credentials loaded from environment variables

The system MUST read AWS configuration exclusively from environment variables. No AWS access keys, secret keys, bucket names, or regions SHALL be hardcoded in Python source or committed settings files.

#### Scenario: Required environment variables

- **WHEN** production storage is initialized
- **THEN** the following variables are read: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`

#### Scenario: Missing credentials in production

- **WHEN** `DJANGO_ENV=prod` and required AWS variables are missing
- **THEN** Django startup or first media operation fails with a clear configuration error (not silent fallback to local disk)

### Requirement: Local development uses filesystem media by default

When `DJANGO_ENV` is not `prod` (default `local`), the system MUST continue using local `MEDIA_ROOT` filesystem storage unless an explicit opt-in env flag enables S3 for testing.

#### Scenario: Local developer upload

- **WHEN** a developer runs the server with `DJANGO_ENV=local` and uploads an image
- **THEN** the file is saved under `BASE_DIR/media/` with the existing `upload_to` path
- **AND** `DEBUG=True` serves media via `/media/` URL as today

### Requirement: Static files remain on WhiteNoise in production

Production static file serving MUST NOT be migrated to S3 as part of this change. `STATICFILES_STORAGE` SHALL remain `whitenoise.storage.CompressedManifestStaticFilesStorage` in `prod.py`.

#### Scenario: Static assets unchanged

- **WHEN** `collectstatic` runs in production
- **THEN** static files are collected to `STATIC_ROOT` and served by WhiteNoise
- **AND** no S3 static backend is configured

### Requirement: Safe migration of existing local media to S3

The system MUST provide a management command `migrate_media_to_s3` that uploads existing files from local `MEDIA_ROOT` to S3 while preserving folder structure and skipping files that already exist in S3.

#### Scenario: Upload local file to S3

- **WHEN** operator runs `python manage.py migrate_media_to_s3` with valid AWS credentials
- **THEN** each file under `media/` is uploaded to S3 with the same relative key (e.g. `media/profiles/a.jpg` → S3 key `profiles/a.jpg`)
- **AND** progress is reported per file or directory

#### Scenario: Skip existing S3 objects

- **WHEN** a file with the same S3 key already exists
- **THEN** the command skips upload for that file (no overwrite, no duplicate)

#### Scenario: Handle upload errors safely

- **WHEN** an individual file upload fails (permissions, network, etc.)
- **THEN** the command logs the error and continues with remaining files
- **AND** exits with a non-zero status if any uploads failed

### Requirement: API image URLs are publicly accessible HTTPS links

In production, API responses that include image or file fields MUST return absolute HTTPS URLs that clients can load directly in a browser without routing through the Django app.

#### Scenario: Meal list API response

- **WHEN** client requests meal list in production
- **THEN** `meal_thumbnail` field value is a full `https://` S3 URL
- **AND** opening the URL in a browser returns the image (bucket policy allows public read for media objects)

#### Scenario: Serializer absolute URL helper compatibility

- **WHEN** a serializer calls `request.build_absolute_uri(field.url)` and `field.url` is already an absolute S3 URL
- **THEN** the returned URL remains a valid absolute HTTPS URL (no double-prefix)

### Requirement: Secrets not committed to version control

The `.env` file MUST be gitignored. `.env.example` MUST document AWS variable names with empty placeholder values. No AWS secrets SHALL appear in tracked Python files.

#### Scenario: Gitignore protection

- **WHEN** developer creates a `.env` file with AWS credentials
- **THEN** git does not track `.env`

#### Scenario: Example env template

- **WHEN** a new developer clones the repository
- **THEN** `.env.example` lists `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME` with empty values
