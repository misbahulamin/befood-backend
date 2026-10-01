# Guest Meal Order System — Frontend & Mobile Integration Guide

**Version:** v1 (2026-09-30)
**Backend base URL:** `<API_HOST>/api/v1/guest-meals/`
**Auth:** Verified customer JWT (same as meal home). `Authorization: Bearer <token>`
**Timezone:** All dates in `Asia/Dhaka`, format `YYYY-MM-DD`. Timezone-naive date strings only.
**Share with:** Web frontend team + Mobile (Flutter/React Native) team.

---

## 1. Ami ki ki implement korechi (Backend summary)

| # | Feature | Details |
|---|---------|---------|
| 1 | Settings foundation | `OrderWalletSettings.guest_meal_box_price` (default 10.00 BDT), `guest_meal_monthly_limit` (default 10). Admin editable via `GET/PATCH /api/v1/web/orders/order-wallet-settings/` |
| 2 | `GuestMealOrder` model | Fields: customer, subscription, delivery (nullable FK), `service_date`, `meal_period` (lunch/dinner), quantity, price snapshots (`base_meal_price`, `box_price`, `unit_price`, `total_amount`), status (scheduled/delivered/cancelled), `wallet_transaction`, `idempotency_key` (unique per customer), `public_id` |
| 3 | Pricing | `unit = published slot final_meal_price + box_price`, `total = unit × quantity`. All snapshots frozen at purchase. Never accept price from client |
| 4 | Payment | Wallet debit at create time (`PAYMENT`, `commission_first`, metadata `purpose=guest_meal`). Floor rule: `recharge_balance − total >= meal_stop_threshold` (inclusive pass) |
| 5 | Monthly quota | `SUM(quantity)` of countable statuses (scheduled/delivered) in Asia/Dhaka calendar month of `created_at`. Enforced atomically with `select_for_update` |
| 6 | Eligibility | Active subscription required; `date >= business_today`; period must be in subscription preference; meal-off cutoff (`is_past_meal_cutoff`); published slot with price; qty 1–10 per request + remaining quota; wallet not frozen + sufficient funds |
| 7 | Atomic create + idempotency | `transaction.atomic()`: replay on same key+payload → `200 + idempotent_replay:true`; same key+different payload → `409 IDEMPOTENCY_CONFLICT` |
| 8 | Delivery/kitchen wiring | Linked to subscription `OrderDelivery` stop; rider board `guest_quantity` additive; kitchen `get_demand` includes guest units in `expected/final_cooking_count`; parent deliver flips scheduled guests → delivered; no re-charge of guest total on deliver |
| 9 | History | Admin Customer-360 activity event `guest_meal_ordered`; customer list/detail APIs |
| 10 | Docs + tests | Backend/frontend/wallet docs, OpenAPI tags `Guest Meals`, `orders/tests/test_guest_meal.py` |

---

## 2. API Contract (5 endpoints)

Base: `/api/v1/guest-meals/`

| Step | Method | Path | Auth | Side effect |
|------|--------|------|------|-------------|
| 1 Usage | `GET` | `/api/v1/guest-meals/usage/` | verified customer | none |
| 2 Preview | `POST` | `/api/v1/guest-meals/preview/` | verified customer | none (quote only) |
| 3 Create | `POST` | `/api/v1/guest-meals/` | verified customer | wallet debit + row create |
| 4 List | `GET` | `/api/v1/guest-meals/?page=1&page_size=20` | verified customer | none (paginated) |
| 5 Detail | `GET` | `/api/v1/guest-meals/{public_id}/` | verified customer | none |

### 2.1 GET usage

```http
GET /api/v1/guest-meals/usage/
Authorization: Bearer <token>
```

Response `200`:

```json
{
  "calendar_month": "2026-09",
  "monthly_limit": 10,
  "used_quantity": 6,
  "remaining_quantity": 4
}
```

Use this to gate the UI. If `remaining_quantity == 0` → disable order button with message.

### 2.2 POST preview (no charge)

```http
POST /api/v1/guest-meals/preview/
Authorization: Bearer <token>
Content-Type: application/json

{ "date": "2026-09-30", "meal_period": "lunch", "quantity": 2 }
```

Response `200`:

```json
{
  "eligible": true,
  "date": "2026-09-30",
  "meal_period": "lunch",
  "quantity": 2,
  "base_meal_price": "80.00",
  "box_price": "10.00",
  "unit_price": "90.00",
  "total_price": "180.00",
  "monthly_limit": 10,
  "monthly_used": 6,
  "monthly_remaining": 4,
  "monthly_remaining_after_order": 2,
  "recharge_balance": "1000.00",
  "meal_stop_threshold": "200.00",
  "recharge_balance_after": "820.00",
  "subscription_public_id": "uuid",
  "cutoff_passed": false
}
```

> Preview is NOT a reservation. Cutoff can pass between preview and create. Always handle `422` on create even after successful preview.

### 2.3 POST create (charges wallet)

```http
POST /api/v1/guest-meals/
Authorization: Bearer <token>
Idempotency-Key: 7c9e6679-7425-40de-944b-e07fc1f90ae7
Content-Type: application/json

{ "date": "2026-09-30", "meal_period": "lunch", "quantity": 2 }
```

- Generate a fresh UUID v4 per user attempt. Send as `Idempotency-Key` header.
- Network retry → resend SAME key + SAME body.
- New order (different date/period/qty) → NEW key.
- First success → `201`. Replay → `200` with `"idempotent_replay": true`. Key conflict → `409`.

Response `201` (same shape for `200` replay):

```json
{
  "public_id": "uuid",
  "date": "2026-09-30",
  "meal_period": "lunch",
  "quantity": 2,
  "base_meal_price": "80.00",
  "box_price": "10.00",
  "unit_price": "90.00",
  "total_price": "180.00",
  "status": "scheduled",
  "subscription_public_id": "uuid",
  "delivery_public_id": "uuid-or-null",
  "wallet_transaction_public_id": "uuid-or-null",
  "created_at": "2026-09-30T10:00:00+06:00",
  "monthly_limit": 10,
  "monthly_used": 8,
  "monthly_remaining": 2,
  "monthly_remaining_after_order": 2,
  "idempotent_replay": false
}
```

### 2.4 GET list

```http
GET /api/v1/guest-meals/?page=1&page_size=20
```

Standard DRF pagination: `{ count, next, previous, results: [...] }`. Each item = create-response shape. Ordered `-created_at`.

### 2.5 GET detail

```http
GET /api/v1/guest-meals/{public_id}/
```

Returns single order or `404 { "detail": "Guest meal not found." }`.

---

## 3. Request validation (client must enforce + server revalidates)

| Field | Rule |
|-------|------|
| `date` | Required, `YYYY-MM-DD`, must be `>=` today (Asia/Dhaka). Past date → `422 INVALID_DATE` |
| `meal_period` | Required, `lunch` \| `dinner` only. Must be covered by subscription (`both` covers all). Else `422 UNSUPPORTED_MEAL_PERIOD` |
| `quantity` | Required int, `1–10` per request AND `<= remaining_quantity`. Else `422 INVALID_QUANTITY` / `MONTHLY_LIMIT_EXCEEDED` |

Do NOT send: prices, wallet balance, subscription_id, monthly counts. Server ignores/derives them.

---

## 4. Error codes (show these messages to user)

All domain errors: `{ "detail": "<human message>", "error_code": "<CODE>" }`

| HTTP | `error_code` | Meaning | UI message suggestion |
|------|--------------|---------|----------------------|
| 422 | `NO_ACTIVE_SUBSCRIPTION` | No active plan | "Guest meal needs an active subscription" |
| 422 | `UNSUPPORTED_MEAL_PERIOD` | Period not in plan | "Your plan doesn't include dinner" |
| 422 | `CUTOFF_PASSED` | Meal-off deadline passed | "Today's cutoff passed, pick another date" |
| 422 | `PRICE_UNAVAILABLE` | No published menu/price | "Menu not published for this date yet" |
| 422 | `MONTHLY_LIMIT_EXCEEDED` | Quota over | "Monthly guest limit reached (X of Y used)" |
| 422 | `MEAL_STOP_FLOOR` | Would breach stop threshold | "Balance would drop below minimum — recharge first" |
| 422 | `INSUFFICIENT_FUNDS` | Not enough spendable | "Insufficient wallet balance" |
| 422 | `WALLET_FROZEN` | Frozen | "Wallet is frozen, contact support" |
| 422 | `INVALID_DATE/QUANTITY/...` | Bad input | Show `detail` |
| 409 | `IDEMPOTENCY_CONFLICT` | Key reused wrongly | "Duplicate request — generate new key" (dev bug) |
| 404 | — | Not own order | "Order not found" |

DRF validation errors (missing field) return standard `{ field: [...] }` with `400`.

---

## 5. Recommended UX flow (Web + Mobile same)

```
[Meal Home / Guest CTA]
   → GET usage → show "X of Y guest meals left this month"
   → Date picker (default tomorrow, min today, block past)
   → Period toggle (lunch/dinner — disable option not in plan)
   → Qty stepper (1..min(10, remaining))
   → [Preview] → bottom-sheet: unit/total breakdown + balance-after + remaining-after
   → [Confirm] → POST create with fresh Idempotency-Key
   → success → toast + refresh usage + navigate to list/detail
   → 422 → inline error from detail/error_code table above
```

Rules:
1. Always `usage → preview → create`. Never skip preview.
2. Refresh `usage` after every successful create.
3. Disable confirm button while request in-flight (prevent double tap).
4. On timeout/no-network → retry with SAME key (safe). On user-edited payload → NEW key.
5. Display money as strings with 2 decimals (`"90.00"`), currency BDT.
6. Meal-OFF day still allows guest order (don't block). Guest food still cooks.
7. No separate delivery tracking UI — guest rides with the regular slot stop.

---

## 6. Flutter / React Native snippets

```dart
// 1. Usage
final usage = await dio.get('/api/v1/guest-meals/usage/');
// usage.data => { monthly_limit, used_quantity, remaining_quantity }

// 2. Preview
final preview = await dio.post('/api/v1/guest-meals/preview/', data: {
  'date': '2026-09-30', 'meal_period': 'lunch', 'quantity': 2,
});

// 3. Create (uuid package for key)
final key = const Uuid().v4();
try {
  final res = await dio.post('/api/v1/guest-meals/', data: body,
    options: Options(headers: {'Idempotency-Key': key}));
} on DioException catch (e) {
  if (e.response?.statusCode == 422) showError(e.response?.data['detail']);
  // on timeout: retry with SAME key
}
```

```typescript
// React Native / Web (fetch)
const key = crypto.randomUUID();
const res = await fetch('/api/v1/guest-meals/', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}`, 'Idempotency-Key': key },
  body: JSON.stringify({ date, meal_period, quantity }),
});
```

---

## 7. Rider / Kitchen / Admin notes (for awareness, no action)

- Rider today-board rows now include `guest_quantity` (add to `meal_quantity` for box count).
- Kitchen demand `expected_meal_count` / `final_cooking_count` already include guest units.
- Admin: box price + monthly limit at `GET/PATCH /api/v1/web/orders/order-wallet-settings/` → `{ guest_meal_box_price, guest_meal_monthly_limit }`.
- No cancel/refund in v1. No guest order for non-subscribers. No push notification in v1.

---

## 8. Test checklist for QA

- [ ] usage shows correct month/limit/remaining
- [ ] preview shows correct `unit = base + box`
- [ ] create debits wallet exactly `total`, floor enforced
- [ ] monthly quota blocks over-limit (422 MONTHLY_LIMIT_EXCEEDED)
- [ ] cutoff date blocks (422 CUTOFF_PASSED)
- [ ] same Idempotency-Key replay → 200 + same public_id, no double charge
- [ ] list/detail only show own orders
- [ ] past date rejected

---

## 9. OpenAPI / Postman

- Swagger: `<API_HOST>/api/schema/swagger-ui/` → tag `Guest Meals`
- Import paths directly; request/response shapes above match serializers exactly.
