## Context

Symptoms on production (`https://api.befood.com.bd`):

- Admin frontend `PATCH /meals/<public_id>/` with `multipart/form-data` returns **`413 Request Entity Too Large`**.
- Local `runserver` meal thumbnail upload succeeds.
- Django shell / `default_storage` write to `core.storage.S3MediaStorage` succeeds.

This pattern strongly indicates the request is rejected by the **reverse proxy (nginx on EC2)** before Django validation or S3, not by django-storages.

Current app contract (already aligned FE/BE):

| Layer | Limit | Location |
|-------|--------|----------|
| Backend validation | 5MB | `meals/services/meal_image.py` → `MAX_IMAGE_SIZE_BYTES` |
| Frontend validation | 5MB | `befood-frontend` → `MAX_MEAL_IMAGE_SIZE_BYTES` |
| Django defaults | memory spill at ~2.5MB | does **not** return HTTP 413 |
| nginx (typical default) | **1m** | returns **413** |

Frontend meal path already looks correct:

- `adminMealsApi.updateAdminMeal` builds `FormData` when `meal_thumbnail` is a `File`.
- `adminApi` interceptor deletes `Content-Type` for `FormData` so the browser sets the multipart boundary.
- Zod rejects files >5MB before submit.

Constraints: S3 setup stays as-is; meal API field contract stays `meal_thumbnail`; product max remains 5MB unless product changes it. Nginx config today lives on the EC2 host (deploy workflow only runs `nginx -t` / reload), not necessarily in this git repo.

## Goals / Non-Goals

**Goals:**

- Stop production `413` for valid meal thumbnails (≤5MB multipart).
- Keep proxy body limit ≥ product image max (recommend ≥10MB headroom for multipart overhead).
- Optionally set explicit Django upload size settings for clarity, still validating at 5MB in meal serializers.
- Confirm frontend meal upload path; fix only if a real client bug is found.
- Document ops steps to verify and prevent regression.

**Non-Goals:**

- Changing S3 backends, buckets, or URL strategy.
- Raising the product thumbnail max above 5MB.
- Reworking all other multipart endpoints (blogs, inventory, etc.) beyond applying the same proxy limit globally.
- Moving nginx config into the repo unless a minimal checked-in snippet is already the team’s preferred ops pattern (optional stretch).

## Decisions

### 1. Treat `413` as a gateway body-size issue first

**Decision:** Primary fix is raise nginx `client_max_body_size` (site or `http`/`server` block for `api.befood.com.bd`) to at least **10m** (headroom over 5MB file + multipart fields).

**Rationale:** HTTP 413 with HTML/nginx error bodies is classic proxy rejection; Django app validation returns 400 with field errors; S3 failures surface as 5xx/storage errors after the body is accepted.

**Alternatives considered:** Blame S3 / frontend FormData first — rejected because local multipart and shell S3 both work, and frontend FormData/`Content-Type` handling for meals is already correct.

### 2. Align Django settings with the 5MB product limit (defensive)

**Decision:** Set in shared/base or prod settings something like:

- `DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024` (or ≥5MB + margin)
- Keep meal-level validation at 5MB via `validate_image_size`

**Rationale:** Prevents accidental reliance on Django’s smaller memory defaults; does not replace proxy config (Django never sees the body if nginx returns 413).

**Alternatives considered:** Change only nginx — acceptable minimum, but explicit Django settings make the contract visible in code reviews.

### 3. Frontend: verify first, change only if broken

**Decision:** Smoke-check `AdminMealForm` → `updateAdminMeal` → `adminApi` against production after proxy fix. Do not change meal FormData construction unless a bug is proven (e.g. wrong field name, forced `Content-Type`, double-encoding).

**Rationale:** Current code matches backend docs (`meal_thumbnail`, multipart on create; multipart on patch when file present). Other admin APIs that set `Content-Type: multipart/form-data` manually are a separate risk and out of scope for meal thumbnails.

**Alternatives considered:** Add client-side image compression — deferred; nice-to-have if admins routinely pick near-limit camera photos, not required to fix 413.

### 4. Document ops verification, prefer host nginx edit (+ optional repo snippet)

**Decision:** Document the exact nginx directive and reload steps in backend ops docs (e.g. extend `core/docs/backend/s3-media-storage.md` or a small `multipart-uploads.md`). Optionally add a sample `deploy/nginx/` snippet later; immediate fix is on the live server config that deploy already reloads.

**Rationale:** Deploy workflow already assumes host nginx; shipping a full nginx rewrite is out of scope for this bugfix.

## Risks / Trade-offs

- **[Risk] Wrong nginx site file edited** → Mitigation: confirm which `server_name` serves `api.befood.com.bd`, run `nginx -t`, then reload; verify with a ~2–4MB PATCH.
- **[Risk] Another layer (Cloudflare, ALB, CDN) also caps body size** → Mitigation: if nginx is raised and 413 persists, inspect response headers/body and upstream limits next.
- **[Risk] Raising body limit enables larger abuse payloads** → Mitigation: keep meal app validation at 5MB; auth still required for `/meals/` write; rate limiting remains separate.
- **[Risk] Frontend appears “broken” while gateway rejects** → Mitigation: document that 413 is infra; surface clearer admin error copy only if product wants (optional).

## Migration Plan

1. On EC2: set `client_max_body_size 10m;` for the API server block; `sudo nginx -t`; `sudo systemctl reload nginx`.
2. Deploy any Django settings clarification if included in this change; restart gunicorn.
3. Smoke-test from admin UI: replace `MealCategory` thumbnail with a file under 5MB; confirm `200` and S3 URL in response.
4. Negative check: file >5MB should fail at frontend zod or Django `400` with thumbnail validation — **not** `413`.
5. Rollback: restore previous nginx directive and reload if unexpected issues (unlikely for a higher limit).

## Open Questions

- Exact path of the live nginx config on EC2 (confirm during apply: `/etc/nginx/sites-enabled/...`).
- Whether any CDN/WAF in front of the API also enforces a body limit.
- Whether the team wants a checked-in nginx sample under `deploy/` in this repo for future hosts.
