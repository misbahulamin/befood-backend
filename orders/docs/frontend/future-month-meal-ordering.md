# Frontend: future-month meal ordering (retired)

## What changed

The 13-month **Order Now** picker (`GET /orders/orderable-months/`, `POST /orders/` with `year`/`month`) is **retired**. Customers subscribe once; see [`customer-meal-subscription.md`](customer-meal-subscription.md).

Stale clients that still call those endpoints receive `409` with `error_code: SUBSCRIBE_REQUIRED`.

Menu **preview** without a subscription is unchanged:

```http
GET /meals/order-menu-preview/?meal_public_id=<uuid>&year=2026&month=8
```

After subscribe, the ownership-scoped calendar is:

```http
GET /meals/my-package-menu/?year=2026&month=8
```

Unpublished months return `schedule_published: false` and empty `days` — do not ask the customer to re-order; slots appear when the menu is published and the daily ensure job (or a current/detail fetch) runs.


1. Show a **month picker** (default = current month).
2. Check whether that month’s menu is **published**.
3. If published → show menu preview and allow confirm.
4. If not → show a friendly message (do not call create).
5. On confirm, send `year` + `month` with the order so the backend saves `order_month`.

Existing rules still apply **for the selected month**:

- At most one non-cancelled package per `order_month`.
- Wallet balance ≥ `min_wallet_balance_to_order` (eligibility only — no debit on create).

**Target client:** Customer mobile and web.

---

## Auth / headers

```http
Authorization: Token <customer-token>
Content-Type: application/json
```

Optional: `X-Client-Type: mobile` | `web`

---

## Recommended UI workflow

```text
1. User taps Order Now on a meal package
2. GET /orders/orderable-months/?meal_public_id=<uuid>
3. Render month list; pre-select the entry with is_current === true
4. On month change:
   - If !is_published → show unpublished message; disable Confirm
   - If has_order → show “already ordered this month”; disable Confirm
   - If is_published && !has_order → GET /meals/order-menu-preview/... then show menu
5. User taps Confirm → POST /orders/ with meal_public_id + year + month
6. Handle 400 errors (month lock, wallet, unpublished race, invalid month)
```

---

## API sequence

### 1) Load month picker

```http
GET /orders/orderable-months/?meal_public_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
Authorization: Token <token>
```

**200 response**

```json
{
  "meal_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "meal_name": "Regular Monthly",
  "months": [
    {
      "year": 2026,
      "month": 7,
      "order_month": "2026-07",
      "label": "July 2026",
      "is_current": true,
      "is_published": true,
      "has_order": false
    },
    {
      "year": 2026,
      "month": 8,
      "order_month": "2026-08",
      "label": "August 2026",
      "is_current": false,
      "is_published": false,
      "has_order": false
    }
  ]
}
```

Always **13** entries: current month through +12.

| Field | UI use |
|-------|--------|
| `label` | Display text (or format `year`/`month` in Bangla yourself) |
| `is_current` | Default selection |
| `is_published` | Gate menu preview + Confirm |
| `has_order` | Disable Confirm; show already-ordered state |
| `year` / `month` | Pass to preview + create |

**Errors:** `401` unauthenticated · `404` unknown meal · `400` missing `meal_public_id`

---

### 2) Preview menu for selected month

```http
GET /meals/order-menu-preview/?meal_public_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee&year=2026&month=8
Authorization: Token <token>
```

Omit `year`/`month` to preview the **current** month. Both required together if either is sent.

**Published**

```json
{
  "year": 2026,
  "month": 8,
  "meal_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "meal_name": "Regular Monthly",
  "schedule_published": true,
  "days": [
    {
      "service_date": "2026-08-01",
      "slots": [
        {
          "meal_period": "lunch",
          "ingredients": [
            { "id": 1, "name": "Chicken", "product_role": "main" }
          ]
        }
      ]
    }
  ]
}
```

**Not published yet** (still `200` — use for empty state)

```json
{
  "year": 2026,
  "month": 9,
  "meal_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "meal_name": "Regular Monthly",
  "schedule_published": false,
  "days": []
}
```

> **Note:** `GET /meals/my-package-menu/` stays for **after** the customer already has an order. Without an order it returns `packages: []` even if a menu is published. Use **order-menu-preview** during Order Now.

---

### 3) Confirm order

```http
POST /orders/
Authorization: Token <token>
Content-Type: application/json

{
  "meal_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  "year": 2026,
  "month": 8,
  "customer_note": ""
}
```

Omit `year`/`month` to order for the **current** month (backward compatible).

**201** includes `order_month`, `order_start_date`, `order_end_date` for the selected month.

Example: ordered on 31 July 2026 for August → `order_month: "2026-08"`.

---

## Unpublished menu — UI copy

Show when `is_published === false` or preview `schedule_published === false` (and disable Confirm).

**English (matches API create error):**

> This month's menu has not been published yet. Once the menu is published, you will be able to place your order.

**Bangla (client-side localization):**

> এই মাসের Menu এখনো প্রকাশ করা হয়নি। Menu প্রকাশ হলে আপনি Order করতে পারবেন।

On create, the same English string may appear under `non_field_errors` if the menu was unpublished between picker load and confirm — re-fetch orderable-months / preview.

---

## Wallet + month-lock integration

Before enabling Confirm (in addition to publish checks):

1. `GET /wallet/` → compare `balance` to `min_wallet_balance_to_order`; if `status === "frozen"`, block order.
2. Respect `has_order` on the selected month from orderable-months.
3. Always handle server `400` — client checks are hints only.

See also: [order-eligibility-wallet-min-balance.md](./order-eligibility-wallet-min-balance.md)

---

## Error cheat sheet (`POST /orders/`)

| Symptom in response | UI action |
|---------------------|-----------|
| `Both year and month are required together` | Always send both or neither |
| `past month` / `too far in the future` | Restrict picker to API month list |
| `menu has not been published` | Unpublished empty state; disable Confirm |
| `already have a meal package for this month` | Show already-ordered for that month |
| `Insufficient wallet balance` | Prompt recharge |
| `wallet is frozen` | Support / wait messaging |

---

## Month picker UX checklist

- [ ] Default selection = `is_current`
- [ ] List built from API (do not invent months client-side only)
- [ ] Unpublished → friendly message, no create
- [ ] Published → preview then confirm with `year`/`month`
- [ ] Surface wallet + month-lock errors after submit

---

## Related docs

- Backend: `orders/docs/backend/future-month-meal-ordering.md`
- Package menu (post-order): `meals/docs/frontend/customer-package-menu.md`
- OpenSpec: `openspec/changes/future-month-meal-ordering/`
