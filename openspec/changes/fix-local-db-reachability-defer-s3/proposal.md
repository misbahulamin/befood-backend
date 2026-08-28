## Why

`python manage.py makemigrations` fails or hangs because local Django settings point at a production RDS host (`befood-postgres-prod...`) that is unreachable from the developer machine (TCP timeout). Production settings also hardcode DB credentials, contain a syntax error on `HOST`, and force S3 media validation before S3 is ready. We need a safe local/prod settings split so migrations, tests, and deploys can run, with S3 deferred until credentials are verified later.

## What Changes

- Restore **local** database config to env-driven local Postgres (or documented local defaults), not production RDS.
- Fix **prod** `DATABASES`: correct syntax, remove hardcoded secrets, use `DB_*` env vars via `python-decouple`.
- Temporarily **disable / comment out** production S3 media wiring (`validate_aws_media_settings`, `STORAGES = PROD_STORAGES`, and related credential usage) so app boot and migrate work without S3; leave clear comments to re-enable later.
- Ensure `.env.example` documents `DJANGO_ENV`, `DB_*`, and deferred S3 flags without real secrets.
- Verify with `makemigrations` / targeted tests; then `migrate` against a reachable DB; push the fix to GitHub `main` after success.
- **BREAKING** (ops only): anyone who relied on `local.py` talking to prod RDS must switch to VPN/bastion or a local DB — intentional.

## Capabilities

### New Capabilities

- `django-env-database-settings`: Local vs prod settings load DB from environment; local never requires unreachable prod RDS; prod never embeds passwords in source.
- `deferred-s3-media-boot`: Production (and optional local) can boot and run management commands without requiring live S3 credentials until the team re-enables them.

### Modified Capabilities

- (none — no existing OpenSpec API capability requirements change)

## Impact

- `core/settings/local.py`, `core/settings/prod.py`, possibly `core/settings/base.py` / `aws_media.py` usage
- `.env.example` (and operator `.env` locally — not committed)
- Local developer workflow: `makemigrations`, `migrate`, `test`
- Production deploy: must set `DJANGO_ENV=prod` and `DB_*`; S3 remains off until uncommented
- No public API contract changes
- Git: commit + push to `main` only after tests and migrate succeed (per user request in apply phase)
