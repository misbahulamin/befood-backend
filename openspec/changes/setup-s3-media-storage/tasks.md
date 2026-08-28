## 1. Verify dependencies and env template

- [x] 1.1 Confirm `django-storages` and `boto3` remain in `requirements.txt` (no version pin change unless required)
- [x] 1.2 Confirm `storages` remains in `INSTALLED_APPS` in `core/settings/base.py`
- [x] 1.3 Ensure `.env.example` documents `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_S3_CUSTOM_DOMAIN`, `USE_S3_MEDIA=false` with empty/placeholder values only (no real secrets)

## 2. Clean shared settings (`base.py`)

- [x] 2.1 Remove duplicate early `STATIC_URL` / `MEDIA_URL` / `MEDIA_ROOT` assignments; keep a single static + media block
- [x] 2.2 Keep AWS settings loaded only via `config(...)` (no hardcoded keys)
- [x] 2.3 Keep `USE_S3_MEDIA` default `False` with `cast=bool`

## 3. Storage backends and MEDIA_URL helper

- [x] 3.1 Confirm `core/storage.py` `S3MediaStorage` defaults (`default_acl=None`, `file_overwrite=False`, `querystring_auth=False`)
- [x] 3.2 Confirm `aws_media.py` keeps media on `S3MediaStorage` and static on WhiteNoise (prod) / filesystem (local)
- [x] 3.3 Add a small helper (in `aws_media.py` or settings) to compute S3 `MEDIA_URL` from custom domain or `https://{bucket}.s3.{region}.amazonaws.com/`
- [x] 3.4 Call `validate_aws_media_settings` only when enabling S3 (bucket + region required; access keys optional for IAM role)

## 4. Local settings toggle

- [x] 4.1 Keep `local.py` enabling `LOCAL_S3_STORAGES` only when `USE_S3_MEDIA=True`
- [x] 4.2 When S3 enabled locally, set `MEDIA_URL` via the helper from task 3.3
- [x] 4.3 When `USE_S3_MEDIA=False`, leave default filesystem media unchanged

## 5. Production settings re-enable

- [x] 5.1 Replace the commented deferred S3 block in `prod.py` with `USE_S3_MEDIA`-gated enablement (same pattern as local)
- [x] 5.2 When `USE_S3_MEDIA=True`, set `STORAGES = PROD_STORAGES`, validate bucket/region, set S3 `MEDIA_URL`
- [x] 5.3 When `USE_S3_MEDIA=False`, do not set S3 STORAGES (filesystem media + existing WhiteNoise middleware remain)
- [x] 5.4 Ensure WhiteNoise middleware injection remains independent of the media toggle

## 6. Migration command and URLs

- [x] 6.1 Verify `migrate_media_to_s3` still preserves relative keys, supports `--dry-run`, skips existing objects, and uses env credentials / default chain
- [x] 6.2 Confirm `core/urls.py` still serves local media only under `DEBUG` (no production local media mount required when S3 is on)

## 7. Tests

- [x] 7.1 Extend or update `core/tests/test_s3_storage.py` for MEDIA_URL helper (custom domain vs bucket endpoint)
- [x] 7.2 Keep/add coverage that default test settings use filesystem storage when `USE_S3_MEDIA` is false
- [x] 7.3 Keep migrate-command dry-run / skip / missing-config tests green
- [x] 7.4 Run `python manage.py test core.tests.test_s3_storage` (and any touched related tests)

## 8. Deploy documentation (no secrets in repo)

- [x] 8.1 Document EC2 host env vars to set (`AWS_*`, `USE_S3_MEDIA`) and prefer IAM instance role when available
- [x] 8.2 Document post-deploy commands: `pip install -r requirements.txt` (if needed), optional `migrate_media_to_s3 --dry-run` / `migrate_media_to_s3`, set `USE_S3_MEDIA=true`, restart gunicorn/systemd, smoke-test upload URL
- [x] 8.3 Document rollback: `USE_S3_MEDIA=false` + process restart (no DB migrate required)

## 9. Final guardrails check

- [x] 9.1 Confirm no AWS keys committed in code, `.env.example`, or docs
- [x] 9.2 Confirm no model / serializer / API / database migration changes were introduced
- [x] 9.3 Summarize changed files and EC2 commands for the operator
