## Why

BeFood already uses `python-decouple` (`config()`) for many settings, including AWS S3 vars, but `.env` loading is incomplete for process-level env: `core/settings/__init__.py` selects local vs prod with `os.getenv('DJANGO_ENV')`, which does **not** read the project-root `.env` file. Decouple’s default search also depends on the process cwd, so EC2 or alternate working directories can miss `.env`. We need a reliable, project-root `.env` bootstrap that does not conflict with existing `config()` usage or hardcode secrets.

## What Changes

- Audit and keep the existing `python-decouple` loader for typed settings (`config(...)`), including all AWS / `USE_S3_MEDIA` reads already in `base.py`.
- Add an explicit early load of the project-root `.env` (next to `manage.py`) into the process environment so both `os.getenv` and `decouple.config` see the same values on local and EC2.
- Prefer `python-dotenv` `load_dotenv()` only as a **bootstrap** (does not replace `decouple`); install `python-dotenv` if adopted.
- Ensure `DJANGO_ENV` and AWS S3 related vars resolve from `.env` / OS env without any credentials in source.
- Document that `.env` lives at the repo root; no DB/models/API/upload logic changes.

No **BREAKING** API or schema changes. Behavioral fix: settings that previously ignored root `.env` for `os.getenv` (notably `DJANGO_ENV`) will start honoring it when the file is present and OS env does not already set the key.

## Capabilities

### New Capabilities

- `project-root-env-loading`: Reliable loading of project-root `.env` for Django settings selection and env-backed config (including AWS / `USE_S3_MEDIA`), without conflicting with `python-decouple` or hardcoding secrets.

### Modified Capabilities

- (none)

## Impact

- **Settings bootstrap:** `core/settings/__init__.py` (and optionally `manage.py` / `wsgi.py` / `asgi.py` for earliest load)
- **Deps:** add `python-dotenv` if chosen for bootstrap; keep `python-decouple`
- **Docs:** short note in `.env.example` and/or `core/docs/backend/`
- **Out of scope:** models, migrations, APIs, upload code, changing S3 STORAGES logic beyond ensuring env reads work
