# Admin customer management

## Quick summary

Verified-admin **read-only** Customer directory for the Admin Panel. List, search, filter, open a full overview, and load paginated order / meal / meal-off / wallet / activity history under `/api/v1/web/customers/`.

| Method | Path | Who | Purpose |
|--------|------|-----|---------|
| GET | `/api/v1/web/customers/` | Verified admin | Paginated list + search/filters |
| GET | `/api/v1/web/customers/{public_id}/` | Verified admin | Detail / overview + summary metrics |
| GET | `/api/v1/web/customers/{public_id}/active-order/` | Verified admin | Current active package (or `null`) |
| GET | `/api/v1/web/customers/{public_id}/orders/` | Verified admin | Order history |
| GET | `/api/v1/web/customers/{public_id}/meals/` | Verified admin | Delivery / meal history |
| GET | `/api/v1/web/customers/{public_id}/meal-offs/` | Verified admin | Skipped (meal-off) slots |
| GET | `/api/v1/web/customers/{public_id}/wallet-transactions/` | Verified admin | Wallet ledger |
| GET | `/api/v1/web/customers/{public_id}/activity/` | Verified admin | Composed activity feed |

Identifiers use `CustomerProfile.public_id` (UUID). Do not use integer PKs.

## Permissions

| Actor | Access |
|-------|--------|
| Verified admin (`IsVerifiedAdmin`: `ADMIN` group + `AdminProfile.is_verified`, or superuser) | All endpoints |
| Customer / deliveryman / anonymous | `401` or `403` |

Customer “verification status” in responses is **email verification** (`is_email_verified` → `verification_status: verified\|unverified`). It is **not** `AdminProfile.is_verified`.

## Mental model

```text
CustomerProfile (+ User)  → identity, phone, email verify, profile fields
Order (status=active)     → current package
OrderDelivery             → meal history / meal-off (status=skipped)
Wallet + WalletTransaction → balance + spending + history
```

v1 is **read-only** (no ban / force-verify / edit from these APIs).

## List query parameters

Allowlisted only; unknown keys → `400`.

| Param | Notes |
|-------|-------|
| `q` | Search name, email, phone (icontains) |
| `is_active` | `true` / `false` → `User.is_active` |
| `is_email_verified` | `true` / `false` |
| `has_active_order` | `true` / `false` |
| `meal_public_id` | Active order’s package UUID (`package_id` also accepted) |
| `registered_from` / `registered_to` | `YYYY-MM-DD` on `User.date_joined` (inclusive) |
| `sort` | `date_joined`, `-date_joined` (default), `created_at`, `-created_at`, `email`, `-email` |
| `page` / `page_size` | Default page size 20, max 100 |

## Detail / overview fields

Detail includes list fields plus profile attributes, addresses, `summary`, and `active_order`.

**`summary`**

| Field | Meaning |
|-------|---------|
| `total_orders` | Count of all orders |
| `total_meals_delivered` | Deliveries with `status=delivered` |
| `total_meal_offs` | Deliveries with `status=skipped` |
| `total_wallet_spent` | Sum of completed wallet **payment** debits (decimal string) |
| `wallet_balance` | Current balance or `null` if no wallet |
| `wallet_currency` | e.g. `BDT` or `null` |
| `last_order_at` | Latest order `created_at` |
| `last_activity_at` | Max of order / profile / meal-off / wallet activity timestamps |
| `profile_picture_url` | Always `null` in v1 |

**`active_order`** (also on `/active-order/` as `{ "active_order": ... }`)

| Field | Meaning |
|-------|---------|
| `order_public_id` | Order UUID |
| `package_name` | Snapshot name |
| `meal_public_id` | Package UUID |
| `order_status` | Expected `active` |
| `order_start_date` / `order_end_date` | Service window |
| `order_month` | `YYYY-MM` |
| `remaining_meals` | Count of `scheduled` deliveries |
| `customer_name` | Display name |

When there is no active order: `{ "active_order": null }` (`200`).

## History endpoints

All paginated (`count`, `next`, `previous`, `results`).

### Orders

Package snapshots, status, dates, delivered/skipped/remaining counts.

### Meals

Allowlisted filters: `status`, `meal_period` (`lunch`|`dinner`), `service_date_from`, `service_date_to`.

### Meal-offs

Only `skipped` deliveries. Filters: `meal_period`, `service_date_from`, `service_date_to` (not `status`). Includes `skip_source`, `note`.

### Wallet transactions

Empty page (`count=0`) if the customer has no wallet. Types: `recharge`, `withdraw`, `payment`, `refund`, `adjustment`.

### Activity

Composed (not a dedicated audit table): `order_created`, `order_status_changed`, `meal_off`, `wallet_*`. Each item: `event_type`, `occurred_at`, `summary`, `refs`.

## Example: list

```http
GET /api/v1/web/customers/?q=alice&has_active_order=true&page_size=20
Authorization: Token <admin-token>
```

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "public_id": "…",
      "name": "Alice Active",
      "email": "alice@example.com",
      "phone": "1711111111",
      "profile_picture_url": null,
      "is_active": true,
      "account_status": "active",
      "is_email_verified": true,
      "verification_status": "verified",
      "registered_at": "2026-08-01T10:00:00Z",
      "current_package": {
        "order_public_id": "…",
        "package_name": "Regular Package",
        "remaining_meals": 1,
        "order_status": "active"
      },
      "wallet_balance": "400.00"
    }
  ]
}
```

## Errors

| Status | When |
|--------|------|
| `401` | Missing/invalid auth |
| `403` | Authenticated but not verified admin |
| `404` | Unknown customer `public_id` |
| `400` | Unknown/invalid query params |

## Key code

- `user_management.services.admin_customer` — filters, metrics, history querysets, activity composition
- `user_management.api.admin_customer_views.AdminCustomerViewSet`
- `user_management.api.web_urls` mounted at `/api/v1/web/customers/`

## How to verify

```bash
python manage.py test user_management.tests.test_admin_customer_management
```

## OpenSpec

`openspec/changes/admin-customer-management/`
