## ADDED Requirements

### Requirement: Project-root .env is loaded early without replacing python-decouple
The system MUST load the `.env` file from the Django project root (the directory containing `manage.py`) into the process environment before settings modules select `local` vs `prod` or read AWS configuration. Existing `python-decouple` `config()` usage MUST remain the primary typed settings reader and MUST NOT be removed or duplicated for the same keys in a conflicting way.

#### Scenario: .env present next to manage.py
- **WHEN** a `.env` file exists in the project root and Django settings are imported
- **THEN** values from that file MUST be available to process environment / settings readers regardless of the process current working directory (when the settings package can resolve the project root)

#### Scenario: Existing decouple config continues to work
- **WHEN** settings call `config('USE_S3_MEDIA', ...)` or other existing `config(...)` keys
- **THEN** those calls MUST continue to resolve from OS environment and/or `.env` without requiring callers to switch APIs

### Requirement: OS environment wins over .env
When a variable is already set in the real process environment (e.g. systemd on EC2), loading `.env` MUST NOT override that value. Missing `.env` MUST NOT prevent boot when required values are supplied via OS environment.

#### Scenario: systemd Environment= takes precedence
- **WHEN** `USE_S3_MEDIA` (or another key) is set in the OS environment and also present in `.env` with a different value
- **THEN** settings MUST use the OS environment value

#### Scenario: Boot without .env file
- **WHEN** no project-root `.env` file exists but required variables are set in the OS environment
- **THEN** Django settings MUST still import successfully

### Requirement: DJANGO_ENV selection honors project-root .env
`core/settings/__init__.py` MUST resolve `DJANGO_ENV` from the loaded environment (including project-root `.env`) so local vs prod selection is not limited to pre-existing OS env alone.

#### Scenario: DJANGO_ENV=local only in .env
- **WHEN** project-root `.env` contains `DJANGO_ENV=local` and the OS environment does not set `DJANGO_ENV`
- **THEN** Django MUST load local settings

#### Scenario: Default when unset
- **WHEN** `DJANGO_ENV` is unset in both OS env and `.env`
- **THEN** the existing default settings branch behavior MUST remain (document current default; do not silently change production EC2 expectations without an explicit decision)

### Requirement: AWS S3 and USE_S3_MEDIA remain env-only
AWS credentials and S3 toggles MUST be read only from environment / `.env` via the existing settings pattern. Source code MUST NOT hardcode AWS access keys or secret keys. `USE_S3_MEDIA` true/false MUST continue to control S3 vs local media as already implemented; this change MUST NOT alter models, APIs, or upload business logic.

#### Scenario: AWS keys from env
- **WHEN** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, `AWS_S3_REGION_NAME`, `AWS_S3_CUSTOM_DOMAIN`, and `USE_S3_MEDIA` are set in `.env` or OS env
- **THEN** `base.py` (or equivalent shared settings) MUST expose them through `config(...)` without embedding secrets in Python source

#### Scenario: No storage behavior rewrite
- **WHEN** this env-loading change is applied
- **THEN** database, models, API contracts, and existing upload field logic MUST remain unchanged aside from correctly reading env values

### Requirement: Secrets stay out of the repository
The `.env` file MUST remain gitignored. Committed examples MUST use empty or non-secret placeholders only.

#### Scenario: .env not tracked
- **WHEN** a developer adds secrets to project-root `.env`
- **THEN** git MUST NOT track that file (`.gitignore` already covers `.env` or is updated if missing)
