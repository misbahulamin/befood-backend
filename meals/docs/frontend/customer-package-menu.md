# Customer Package Menu API (Frontend)

Authenticated customers can load the **full published monthly lunch/dinner menu** for the meal package they purchased that month. Use this for a calendar / month-plan UI.

This is **not** the same as `GET /meals/today-menu/`, which only returns today's periods after reveal times.

**Target client:** Customer mobile and web.

---

## Auth

| Item | Value |
|------|--------|
| Header | `Authorization: Token <token>` |
| Who | Verified customer (`CUSTOMER` group + verified email + customer profile) |
| Permission | `IsVerifiedCustomer` |

Unauthenticated → `401`.

---

## Endpoint

| Method | Path | Why |
|--------|------|-----|
| `GET` | `/meals/my-package-menu/` | Full monthly menu for the caller's package(s) |

### Query parameters

| Param | Required | Meaning |
|-------|----------|---------|
| `year` | No* | Calendar year, e.g. `2026` |
| `month` | No* | Calendar month `1`–`12` |

\*Omit both to use the **current local month**. If you send one, you must send both. Invalid month or incomplete pair → `400`.

Examples:

```http
GET /meals/my-package-menu/
Authorization: Token <token>

GET /meals/my-package-menu/?year=2026&month=7
Authorization: Token <token>
```

---

## Recommended UI workflow

1. Customer logs in → store Token.
2. (Optional) Confirm package via `GET /orders/current-package/`.
3. Call `GET /meals/my-package-menu/` (optionally with `year` + `month`).
4. If `packages` is empty → show “No meal package for this month.”
5. If `schedule_published` is `false` → show “Menu coming soon” (keep package name).
6. If `schedule_published` is `true` → render `days` as a calendar (group by `service_date`, show lunch/dinner ingredients).
7. Separately call `GET /meals/today-menu/` for “what's for today” with reveal gating.

---

## Success response (`200`)

```json
{
  "year": 2026,
  "month": 7,
  "packages": [
    {
      "meal_public_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
      "meal_name": "Regular Package",
      "order_public_id": "11111111-2222-3333-4444-555555555555",
      "schedule_published": true,
      "days": [
        {
          "service_date": "2026-07-01",
          "meal_period": "dinner",
          "ingredients": [
            {
              "id": 1,
              "name": "Chicken",
              "product_role": "main"
            },
            {
              "id": 3,
              "name": "Rice",
              "product_role": "staple"
            }
          ]
        },
        {
          "service_date": "2026-07-01",
          "meal_period": "lunch",
          "ingredients": [
            {
              "id": 2,
              "name": "Beef",
              "product_role": "main"
            },
            {
              "id": 3,
              "name": "Rice",
              "product_role": "staple"
            }
          ]
        }
      ]
    }
  ]
}
```

### Field meanings

| Field | Meaning |
|-------|---------|
| `year` / `month` | Month the response covers |
| `packages` | One entry per non-cancelled order the customer owns in that month |
| `meal_public_id` | Meal package UUID |
| `meal_name` | Display name |
| `order_public_id` | Customer's order UUID for that package |
| `schedule_published` | `true` only when admin published the monthly schedule |
| `days` | All lunch/dinner slots (no reveal-time filter). Empty when unpublished |
| `service_date` | ISO date `YYYY-MM-DD` |
| `meal_period` | `lunch` or `dinner` |
| `ingredients[].id` | Ingredient integer id (same shape as today-menu) |
| `ingredients[].name` | Display name |
| `ingredients[].product_role` | From the package’s cycle plan line (`main`, `side`, `staple`, …) — not from the ingredient catalog |
| `ingredients[]` filter | Ingredients with `is_customer_visible=false` are omitted |

`days` are ordered by `service_date`, then `meal_period` (string order: `dinner` before `lunch`).

---

## Empty / edge UI states

| Situation | Response hint | UI |
|-----------|---------------|-----|
| No order this month | `packages: []` | “No package” |
| Order exists, menu draft/unpublished | `schedule_published: false`, `days: []` | “Menu coming soon” |
| Cancelled order only | Not included in `packages` | Same as no package |

---

## Errors

| Status | When |
|--------|------|
| `401` | Missing/invalid token |
| `400` | Only `year` or only `month`, or `month` outside 1–12 |
| `403` | Authenticated but no customer profile (rare) |

Example `400` (field errors):

```json
{
  "month": ["Month must be between 1 and 12."]
}
```

---

## Difference from today-menu

| | `my-package-menu` | `today-menu` |
|--|-------------------|--------------|
| Scope | Full month | Today only |
| Reveal times | Not applied | Applied |
| Use for | Calendar / planning | “What's for lunch/dinner now” |

---

## Pre-order menu preview (Order Now)

To show a published monthly menu **before** the customer has an order for that month, use:

`GET /meals/order-menu-preview/?meal_public_id=&year=&month=`

`my-package-menu` remains ownership-scoped and returns empty `packages` when there is no order. Full Order Now month-picker flow: see `orders/docs/frontend/future-month-meal-ordering.md`.

---

## How to verify quickly

1. Login as verified customer with a confirmed order for a month that has a **published** menu schedule.
2. `GET /meals/my-package-menu/?year=YYYY&month=M` → `schedule_published: true` and many `days`.
3. Without auth → `401`.
4. `?month=13` → `400`.
5. Without an order, `my-package-menu` is empty; `order-menu-preview` can still return a published menu for that meal.