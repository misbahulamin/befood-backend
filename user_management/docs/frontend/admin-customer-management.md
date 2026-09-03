# Admin Customer Management — Frontend Integration

## Summary

Admin Panel Customer 360 at `/admin/customers/:publicId`. **Subscription-first** tabs; history lazy-loaded per tab. Overview loads a single lean detail GET — no embedded history arrays.

## Auth

- Verified admin token (`Authorization: Token …`)
- Customer tokens receive `403` on all admin customer routes (including another customer's `public_id`)

## Page flow

1. **Customer list** — `GET /api/v1/web/customers/` with filters
2. **Customer detail** — `GET /api/v1/web/customers/{publicId}/` (overview only)
3. **Tab switch** — enable React Query fetch for that tab's endpoint only

## Tabs

| Tab | Endpoint | Lazy? |
|-----|----------|-------|
| Overview | Detail GET | No (initial load) |
| Active subscription | `…/active-subscription/` | Yes |
| Subscription history | `…/subscriptions/` | Yes |
| Meal history | `…/meals/` | Yes |
| Meal-offs | `…/meal-offs/` | Yes |
| Wallet overview | `…/wallet-overview/` | Yes |
| Wallet history | `…/wallet-transactions/` | Yes |
| Activity | `…/activity/` | Yes |

### Legacy monthly orders

When `summary.has_legacy_orders === true`, show a **collapsed** "Legacy monthly orders" section on the Subscription history tab. Expand loads deprecated `GET …/orders/`.

## Header summary cards (from detail)

- Active subscription package
- Wallet balance
- Meals delivered, total subscriptions
- Customer lifetime value, last payment, last meal, package expiry

## Field mapping (use backend names)

| UI | API field |
|----|-----------|
| Subscription row key | `public_id` |
| Delivered/skipped counts | `delivered_count`, `skipped_count` |
| Address line | `full_address` |
| Allergies | `has_allergy`, `allergy_details`, `restricted_foods` |
| Meal row key | `public_id` |
| Subscription status | `status` (render raw value; tolerate unknown enums) |
| Phone (list + overview) | `phone` as E.164 `+880…` (or `null`); display **as-is** — do **not** prepend another `+880`. WhatsApp links: derive digits from the E.164 value (e.g. `CustomerPhoneWhatsAppLink` / `wa.me`) |

## Wallet support scenario

Wallet overview shows `pending_recharge_amount` separately from `available_balance` so admins can answer "I recharged but balance didn't update."

## Empty states

- No active subscription → "No active subscription"
- No wallet → wallet overview zeros / "No wallet" on overview
- No history rows → tab-specific empty copy; **never** invent placeholder data

## Code locations (`befood-frontend`)

- `src/features/admin/pages/AdminCustomerDetailPage.tsx`
- `src/features/admin/api/adminCustomerApi.ts`
- `src/features/admin/hooks/useAdminCustomers.ts`
- `src/features/admin/types/customerManagementTypes.ts`

## QA matrix

| Customer | Expected |
|----------|----------|
| A — active subscription + wallet + meals | All tabs populated |
| B — cancelled subscription | History visible; active null |
| C — no subscription, no wallet | Empty states |
| D — legacy order only | Subscription empty; legacy collapsible visible |

Cross-customer: Customer A token → Customer B admin URLs → `403`.
