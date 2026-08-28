## Context

BeFood already partially integrated AWS S3 media:

- `django-storages` and `boto3` are in `requirements.txt` and `storages` is in `INSTALLED_APPS`.
- `core/settings/base.py` reads `AWS_*` and `USE_S3_MEDIA` via `decouple.config`.
- `core/storage.py` defines `S3MediaStorage`; `core/settings/aws_media.py` defines `PROD_STORAGES` / `LOCAL_S3_STORAGES`.
- `local.py` already enables S3 when `USE_S3_MEDIA=True`.
- `prod.py` still has the S3 block **commented out** (deferred by `fix-local-db-reachability-defer-s3`).
- `migrate_media_to_s3` and unit tests already exist.

Django is `>=5.2,<5.3`, so configuration MUST use the `STORAGES` dict (not legacy `DEFAULT_FILE_STORAGE` / `STATICFILES_STORAGE` alone).

Constraints from the request: no hardcoded AWS keys; env-only config; static ≠ media; no model/API/DB changes; minimal safe edits; EC2-compatible.

## Goals / Non-Goals

**Goals:**

- Finish a clean, toggleable S3 media setup controlled by `USE_S3_MEDIA`.
- Re-enable production S3 through the same flag (uncomment + align with local).
- Deduplicate messy duplicate `STATIC_*` / `MEDIA_*` assignments in `base.py`.
- When S3 is on, set `MEDIA_URL` (and rely on django-storages `AWS_S3_CUSTOM_DOMAIN`) so `.url` / API absolute URLs work.
- Document EC2 env + post-deploy commands (including optional `migrate_media_to_s3`).

**Non-Goals:**

- Moving static files to S3/CloudFront.
- Changing ImageField/FileField models, serializers, or API contracts.
- Database migrations for storage.
- Cleaning hardcoded DB passwords in `local.py` / `prod.py` (separate concern).
- Rewriting the existing migrate command unless a small bugfix is required.

## Decisions

### 1. Single flag for local and production: `USE_S3_MEDIA`

**Decision:** Both `local.py` and `prod.py` enable S3 media only when `USE_S3_MEDIA=True`. When false, leave Django default filesystem storage.

**Rationale:** Matches the stated requirement; safer production rollout than always-on S3; allows EC2 to set the flag after credentials are verified.

**Alternative considered:** Always-on S3 in `prod.py` — rejected because it conflicts with the explicit toggle and the prior deferral.

### 2. Keep shared AWS reads in `base.py`; keep backends in `aws_media.py`

**Decision:** Continue reading AWS env vars in `base.py`. Keep `PROD_STORAGES` / `LOCAL_S3_STORAGES` and `validate_aws_media_settings` in `aws_media.py`. Call validation only when enabling S3.

**Rationale:** Already matches project structure; avoids duplicating STORAGES dicts.

### 3. Django 5.2 `STORAGES` — media S3, static separate

**Decision:**

```python
# When USE_S3_MEDIA (prod):
STORAGES = {
    "default": {"BACKEND": "core.storage.S3MediaStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# When USE_S3_MEDIA (local):
STORAGES = {
    "default": {"BACKEND": "core.storage.S3MediaStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
```

**Rationale:** Django 4.2+ / 5.x preferred API; keeps WhiteNoise for prod static.

### 4. MEDIA_URL when S3 is enabled

**Decision:** After enabling S3 STORAGES, set:

- If `AWS_S3_CUSTOM_DOMAIN`: `MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"`
- Else: `MEDIA_URL = f"https://{bucket}.s3.{region}.amazonaws.com/"`

Keep `MEDIA_ROOT` defined for the migrate command and local fallback.

**Rationale:** Ensures consistent absolute URLs; django-storages also uses `AWS_S3_CUSTOM_DOMAIN` for `.url`.

### 5. S3MediaStorage defaults stay ACL-free

**Decision:** Keep `default_acl = None`, `file_overwrite = False`, `querystring_auth = False`. Public read via bucket policy (not object ACLs).

**Rationale:** Modern S3 buckets often block ACLs; matches current `core/storage.py`.

### 6. No model / serializer / URL changes

**Decision:** Do not touch meal/blog/announcement upload code. Django `FieldFile.url` already returns absolute S3 URLs; `build_absolute_uri` is a no-op on absolute URLs.

**Rationale:** Minimal safe change; existing tests that override `MEDIA_ROOT` continue to work when S3 is off (default for tests).

### 7. Credentials: prefer IAM role on EC2, keys optional

**Decision:** If `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are empty, boto3/django-storages MUST fall through to the default credential chain (EC2 instance role). Keys remain optional when an IAM role is attached.

**Rationale:** Production best practice; validation only requires bucket + region when S3 is enabled.

### 8. Settings cleanup in `base.py`

**Decision:** Remove duplicate early `STATIC_URL` / `MEDIA_*` lines; keep one Static/Media section plus the AWS block. Do not relocate email or other unrelated settings.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Existing EC2 disk media become unreachable after S3 switch | Run `migrate_media_to_s3 --dry-run` then real upload before or right after enabling the flag; keep disk backup until verified |
| Bucket policy denies public GetObject → broken images | Document required bucket policy; smoke-test a URL in browser |
| Collectstatic / WhiteNoise broken if STORAGES misconfigured | Keep static backend on WhiteNoise; never point staticfiles at S3MediaStorage |
| Tests accidentally hit real S3 | Default `USE_S3_MEDIA=false`; existing `@override_settings(MEDIA_ROOT=...)` |
| Empty custom domain builds bad MEDIA_URL | Only apply custom-domain MEDIA_URL when non-empty |

## Migration Plan

1. Merge code with `USE_S3_MEDIA=false` default (no behavior change on deploy).
2. On EC2: set `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, optional keys or IAM role, optional `AWS_S3_CUSTOM_DOMAIN`.
3. Install deps if needed: `pip install -r requirements.txt` (storages/boto3 already listed).
4. Optional: `python manage.py migrate_media_to_s3 --dry-run` then `python manage.py migrate_media_to_s3`.
5. Set `USE_S3_MEDIA=true`, restart the app process (systemd/gunicorn).
6. Smoke-test admin/API upload and confirm S3 object + HTTPS URL.
7. **Rollback:** set `USE_S3_MEDIA=false`, restart; local/EC2 disk media still available if not deleted; S3 objects remain intact.

## Open Questions

- Confirm whether EC2 already has an IAM instance role for the media bucket (preferred) or will use access keys in host env.
- Confirm whether `AWS_S3_CUSTOM_DOMAIN` (CloudFront / custom host) will be used at go-live or left empty.
