## 1. Dependencies and Environment

- [x] 1.1 Add `django-storages` and `boto3` to `requirements.txt`
- [x] 1.2 Run `pip install django-storages boto3` in local venv and verify import
- [x] 1.3 Add AWS env var placeholders to `.env.example` (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `USE_S3_MEDIA=false`)
- [x] 1.4 Verify `.gitignore` includes `.env` (already present — confirm no `.env` tracked)

## 2. Settings — Base Configuration

- [x] 2.1 Add `'storages'` to `INSTALLED_APPS` in `core/settings/base.py`
- [x] 2.2 Add AWS env var reads in `base.py` using existing `python-decouple` `config()` (no hardcoded values)
- [x] 2.3 Add `AWS_S3_OBJECT_PARAMETERS` cache header and optional `AWS_S3_CUSTOM_DOMAIN` read
- [x] 2.4 Verify `WhiteNoiseMiddleware` is in `MIDDLEWARE` (add after `SecurityMiddleware` if missing)

## 3. Storage Backend

- [x] 3.1 Create `core/storage.py` with `S3MediaStorage` subclass (`public-read`, `file_overwrite=False`, `querystring_auth=False`)
- [x] 3.2 Create `core/management/commands/__init__.py` if missing
- [x] 3.3 Create `core/management/__init__.py` if missing

## 4. Settings — Production (S3 activation)

- [x] 4.1 Update `core/settings/prod.py` with Django 5.1 `STORAGES` dict: `default` → `core.storage.S3MediaStorage`, `staticfiles` → WhiteNoise
- [x] 4.2 Remove legacy standalone `STATICFILES_STORAGE` line (superseded by `STORAGES["staticfiles"]`)
- [x] 4.3 Add startup validation: fail clearly if required AWS vars missing when `DJANGO_ENV=prod`

## 5. Settings — Local Development

- [x] 5.1 Add optional `USE_S3_MEDIA` flag in `local.py` to enable S3 storage for local integration testing
- [x] 5.2 Ensure default local behavior remains filesystem `MEDIA_ROOT` with `/media/` URL serving via `DEBUG=True`

## 6. Media Migration Command

- [x] 6.1 Create `core/management/commands/migrate_media_to_s3.py`
- [x] 6.2 Implement recursive walk of `MEDIA_ROOT`, preserve relative paths as S3 keys
- [x] 6.3 Skip files already in S3 (`head_object` check), no overwrite
- [x] 6.4 Add `--dry-run` flag, progress output, and error-safe continuation
- [x] 6.5 Exit non-zero if any uploads failed; print summary (`uploaded`, `skipped`, `failed`)

## 7. Tests

- [x] 7.1 Create `core/tests/test_s3_storage.py` — verify `prod` settings load `S3MediaStorage` backend
- [x] 7.2 Test `local` settings default to filesystem storage
- [x] 7.3 Test migration command dry-run logic (mock boto3 or use moto)
- [x] 7.4 Verify existing announcement/media tests still pass with `override_settings(MEDIA_ROOT=...)`

## 8. AWS Infrastructure Verification (manual)

- [ ] 8.1 Confirm S3 bucket `befood-production-media` exists in `ap-south-1`
- [ ] 8.2 Configure bucket policy or ACL for public `GetObject` on media objects
- [ ] 8.3 Configure CORS for frontend origins (`befood.com.bd`, `localhost:5173`)
- [ ] 8.4 Create IAM user or EC2 instance role with `PutObject`, `GetObject`, `ListBucket`, `HeadObject`

## 9. EC2 Production Deployment

- [ ] 9.1 Set AWS env vars on EC2 via systemd drop-in or IAM instance role (no `.env` on server)
- [ ] 9.2 Install new packages on EC2: `pip install -r requirements.txt`
- [ ] 9.3 Run `python manage.py migrate_media_to_s3 --dry-run` to preview existing file upload
- [ ] 9.4 Run `python manage.py migrate_media_to_s3` to upload existing local media
- [ ] 9.5 Deploy settings changes and restart gunicorn/systemd service
- [ ] 9.6 Verify new uploads land in S3 and API returns HTTPS S3 URLs

## 10. End-to-End Testing

- [ ] 10.1 Django shell: create ImageField instance, confirm S3 upload and absolute URL
- [ ] 10.2 Admin panel: upload meal thumbnail, avatar, announcement banner — verify in S3 console
- [ ] 10.3 API test: `GET /meals/` and blog endpoints return full S3 URLs
- [ ] 10.4 Browser: open S3 image URL directly — confirm load, permissions, no CORS error
- [ ] 10.5 Production EC2: upload new file post-deploy, confirm S3 object and API response

## 11. Security Review and Git

- [x] 11.1 Grep codebase for hardcoded AWS keys — must return zero matches
- [x] 11.2 Confirm `git status` does not include `.env`
- [x] 11.3 Review all changed files before commit
- [ ] 11.4 Commit: `Configure AWS S3 storage for media files` (only after tests pass)
- [ ] 11.5 Push to remote when user approves
