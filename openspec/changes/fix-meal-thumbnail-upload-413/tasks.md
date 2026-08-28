## 1. Confirm root cause

- [ ] 1.1 On production, capture the `413` response body/headers for `PATCH /meals/{public_id}/` multipart and confirm it originates from nginx (or another gateway), not Django JSON/problem details
- [ ] 1.2 On EC2, locate the nginx `server` block for `api.befood.com.bd` and record current `client_max_body_size` (or absence = default `1m`)
- [ ] 1.3 Reconfirm frontend meal path: `adminMealsApi` FormData + `adminApi` Content-Type deletion + zod 5MB — note any real bugs found (no speculative rewrite)

## 2. Fix production body limits

- [ ] 2.1 Set nginx `client_max_body_size` to at least `10m` on the API server block (or `http` scope if that is the team standard)
- [ ] 2.2 Run `sudo nginx -t` and reload nginx (`sudo systemctl reload nginx`)
- [ ] 2.3 Optionally set Django `DATA_UPLOAD_MAX_MEMORY_SIZE` (≥ 5MB, prefer 10MB) in settings so documented limits match the product contract; restart gunicorn if settings change

## 3. Frontend verification / fixes

- [ ] 3.1 From admin panel against production, replace a `MealCategory` thumbnail with a file ≤5MB and confirm `200` + S3 (or storage) URL
- [ ] 3.2 Confirm client-side rejection for files >5MB (zod message) without relying on `413`
- [ ] 3.3 If a frontend bug is proven (wrong field, forced Content-Type, etc.), fix it in `befood-frontend` and retest; otherwise leave meal upload client code unchanged

## 4. Documentation

- [ ] 4.1 Add or extend backend ops docs with: 413 = proxy body limit checklist, recommended `client_max_body_size`, meal 5MB app validation, local vs production smoke steps
- [ ] 4.2 Cross-link from existing S3 media docs so operators do not debug AWS first for `413`

## 5. Regression safety

- [ ] 5.1 Ensure existing meal multipart tests still pass locally (`meals/tests/test_meals.py` thumbnail cases)
- [ ] 5.2 Smoke-test at least one other authenticated multipart upload path if time permits (e.g. announcement image) to confirm the raised proxy limit did not break other flows
- [ ] 5.3 Record final nginx value and Django settings in the change notes / ops doc for future deploys
