## Why

Production admin meal thumbnail uploads fail with `413 Request Entity Too Large` on `PATCH /meals/<id>/` (multipart), while the same flow works locally and direct Django/`default_storage` writes to S3 succeed. Admins cannot update `MealCategory.meal_thumbnail` from the frontend admin panel against `api.befood.com.bd`, so production media updates are blocked even though S3 storage itself is healthy.

## What Changes

- Diagnose and fix the production request-body size rejection that returns HTTP `413` before (or instead of) Django meal thumbnail validation.
- Align reverse-proxy (nginx on EC2) and Django upload size settings with the existing **5MB** meal image contract (`meals.services.meal_image.MAX_IMAGE_SIZE_BYTES` and frontend `MAX_MEAL_IMAGE_SIZE_BYTES`).
- Verify the frontend admin meal update path (`FormData` + `PATCH /meals/{public_id}/`) does not introduce a client-side failure mode; fix only if a real frontend bug is found.
- Document production upload limits and a short ops checklist so future deploys do not regress `client_max_body_size` (or equivalent).
- Add or update smoke verification steps for multipart meal thumbnail create/update on production after the proxy fix.

## Capabilities

### New Capabilities

- `multipart-upload-body-limits`: Production and Django body/upload limits must allow authenticated multipart meal thumbnail uploads up to the documented 5MB image cap, returning application validation errors (not gateway `413`) for oversized files.
- `meal-thumbnail-upload-ops`: Ops/runbook and verification requirements for meal thumbnail multipart uploads across local vs production (proxy, app, S3), including frontend admin panel smoke checks.

### Modified Capabilities

- (none) — no existing main-spec requirement currently defines production multipart body limits for meal uploads.

## Impact

- **Production infra:** nginx (or other reverse proxy in front of gunicorn) for `api.befood.com.bd` — likely `client_max_body_size` (default often `1m`).
- **Backend:** optional explicit `DATA_UPLOAD_MAX_MEMORY_SIZE` / `FILE_UPLOAD_MAX_MEMORY_SIZE` in settings for clarity and alignment with the 5MB product limit; meal serializers/services unchanged unless a real app-layer bug is found.
- **Frontend (`befood-frontend`):** admin meal APIs (`adminMealsApi`, `AdminMealForm`, zod 5MB validation, `adminApi` FormData `Content-Type` handling) — verify; change only if needed.
- **Deploy:** `.github/workflows/deploy.yml` already reloads nginx; any checked-in nginx snippet or documented server config must stay above the meal image limit.
- **APIs:** no intentional contract change to `POST/PATCH /meals/` fields; success path should reach Django and S3 for files ≤5MB.
- **Out of scope:** redesigning S3 storage, changing thumbnail field name, or raising the product max above 5MB unless product decides otherwise.
