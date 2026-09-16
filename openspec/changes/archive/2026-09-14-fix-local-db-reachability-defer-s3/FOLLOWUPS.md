# Follow-ups (ops)

## Credential rotation

Passwords previously committed in settings (e.g. RDS `Befood459`, old Render DB password in comments) should be rotated on any still-active hosts. Prefer env-only secrets going forward.

## Re-enable S3 media

1. Uncomment the deferred S3 block in `core/settings/prod.py`.
2. Set `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME` on the host.
3. Optionally set `USE_S3_MEDIA=true` for local verification.
4. Smoke-test media upload/download before relying on production traffic.
