## Why

Production currently stores (or falls back to) user-uploaded media on the EC2 local disk while S3 wiring is deferred/commented out. That is fragile for deploy, disk growth, and `DEBUG=False` media serving. The project already has `django-storages`, `boto3`, `S3MediaStorage`, and env reads — they need to be finished cleanly so `USE_S3_MEDIA` toggles S3 vs local without hardcoding credentials or breaking existing uploads.

## What Changes

- Complete and clean AWS S3 media configuration using existing `.env` / `python-decouple` pattern (`AWS_*`, `USE_S3_MEDIA`).
- When `USE_S3_MEDIA=True`, route Django default file storage to S3 for all ImageField/FileField uploads; keep static files on WhiteNoise / filesystem (not S3).
- When `USE_S3_MEDIA=False`, keep current local `MEDIA_ROOT` behavior unchanged.
- Re-enable production S3 via the same `USE_S3_MEDIA` flag (replace the deferred commented block in `prod.py`).
- Deduplicate / tidy `STATIC_*` and `MEDIA_*` settings in `base.py`; set `MEDIA_URL` correctly when S3 (and optional custom domain) is active.
- Preserve existing `upload_to` paths, models, APIs, and serializers — no schema or contract changes.
- Keep / lightly verify `migrate_media_to_s3` for one-time EC2 local → S3 copy.
- Document EC2 env vars and post-deploy commands (restart, optional migrate command, smoke checks).

No **BREAKING** API field removals. Behavioral note: with S3 on, media URLs become absolute S3/CDN HTTPS URLs instead of relative `/media/...` paths.

## Capabilities

### New Capabilities

- `s3-media-storage`: Toggleable AWS S3 storage for user-uploaded media via env, separate from static files, safe local fallback, and production EC2-compatible activation.

### Modified Capabilities

- (none — no existing main-spec requirement changes; this completes deferred S3 work)

## Impact

- **Settings:** `core/settings/base.py`, `local.py`, `prod.py`, `aws_media.py`
- **Storage:** `core/storage.py` (minor if needed for custom domain / MEDIA_URL)
- **Deps:** already present — `django-storages`, `boto3` in `requirements.txt`
- **Management:** existing `migrate_media_to_s3` (verify / document)
- **Tests:** `core/tests/test_s3_storage.py` (extend for `USE_S3_MEDIA` / MEDIA_URL behavior)
- **Docs:** `.env.example` comments; brief deploy notes in change tasks / backend doc if needed
- **Out of scope:** model migrations, API serializers/endpoints, static-to-S3, DB credential cleanup, hardcoding any AWS keys
