# Environment loading

## Layout

Place `.env` in the **project root** (same directory as `manage.py`).

## How it works

1. **python-dotenv** (`core.load_env.load_project_env`) loads `<project-root>/.env`
   into the process environment with `override=False` (OS / systemd wins).
2. **python-decouple** `config()` in `core/settings/base.py` remains the typed
   reader for flags and secrets (including `AWS_*` and `USE_S3_MEDIA`).
3. Entry points that call `load_project_env()` early:
   - `core/settings/__init__.py` (before `DJANGO_ENV` selection)
   - `manage.py`
   - `core/wsgi.py`
   - `core/asgi.py`

Missing `.env` is fine when variables are set via systemd / host environment.

## EC2

```bash
pip install -r requirements.txt
# Ensure AWS_* / USE_S3_MEDIA / DJANGO_ENV are in host .env or systemd Environment=
sudo systemctl restart gunicorn   # your unit name
```

No database migration is required for env-loading changes.

## Security

Never commit real AWS keys. Keep `.env` gitignored; use `.env.example` placeholders only.
