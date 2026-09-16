## 1. Dependency and audit

- [x] 1.1 Confirm `python-decouple` remains in `requirements.txt` and continues to power `config()` in `base.py`
- [x] 1.2 Add `python-dotenv` to `requirements.txt` (bootstrap only; do not replace decouple)
- [x] 1.3 Confirm `.gitignore` includes `.env` and `.env.example` has empty AWS / `USE_S3_MEDIA` placeholders (no real secrets)

## 2. Early project-root .env bootstrap

- [x] 2.1 In `core/settings/__init__.py`, resolve project root (`Path(__file__).resolve().parent.parent.parent`) and call `load_dotenv(BASE_DIR / '.env', override=False)` before reading `DJANGO_ENV`
- [x] 2.2 Keep `DJANGO_ENV` default as `prod` when unset (after dotenv load) so EC2 without `.env` is not broken
- [x] 2.3 Add the same `load_dotenv(..., override=False)` at the top of `manage.py` (and `wsgi.py` / `asgi.py` if they are production entrypoints)

## 3. Preserve existing env-backed settings

- [x] 3.1 Leave `base.py` AWS / `USE_S3_MEDIA` `config(...)` reads unchanged (no hardcoded credentials)
- [x] 3.2 Confirm `local.py` / `prod.py` S3 toggles still key off `USE_S3_MEDIA` only — no STORAGES rewrite in this change
- [x] 3.3 Do not change models, serializers, APIs, migrations, or upload field logic

## 4. Docs and verification

- [x] 4.1 Document in `.env.example` (and optionally `core/docs/backend/env-loading.md`): `.env` lives next to `manage.py`; dotenv loads it; OS/systemd wins; decouple still used for typed settings
- [x] 4.2 Add or extend a small test that project-root `.env` values are visible after bootstrap when OS env does not set the key (and that OS env wins when set)
- [x] 4.3 Summarize for the operator: changed files, `pip install -r requirements.txt`, EC2 restart commands (no migrate)

## 5. Guardrails

- [x] 5.1 Confirm no AWS keys or secrets appear in committed source or docs
- [x] 5.2 Confirm production can boot with OS env only and no `.env` file
