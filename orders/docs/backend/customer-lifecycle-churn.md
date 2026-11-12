# Customer Lifecycle & Churn Classification

## Quick summary

Shared Asia/Dhaka lifecycle rules live in `orders/services/customer_lifecycle.py`. Every admin customer list, churn list, analytics, and dashboard KPI MUST use these helpers so classifications stay identical.

| Lifecycle | Meaning |
|-----------|---------|
| `never_subscribed` | Zero `CustomerSubscription` rows |
| `unsubscribed` | Had ≥1 subscription ever; no `active` subscription |
| `at_risk` | Has `active` subscription and meets any at-risk rule |
| `won_back` | Active, not at_risk, and has a prior cancel whose churn date is before current `started_on` |
| `active` | Active subscription, not at_risk, not won_back |

**Precedence (mutually exclusive):**  
`never_subscribed` → `unsubscribed` → `at_risk` → `won_back` → `active`

## Churn date

For a cancelled subscription:

1. Prefer `cancel_effective_on`
2. Else Asia/Dhaka calendar date of `cancelled_at`

For an unsubscribed customer’s “churn date”, use the **latest** cancelled subscription’s churn date.

## At-risk rules (any one is enough)

Evaluated in Asia/Dhaka business time for customers with an **active** subscription:

1. **Low-balance blocked days (v1):** currently `meal_service_blocked_low_balance`, count service dates from `meal_service_blocked_at` (Dhaka date) through today inclusive, intersected with the last 7 days; **plus** distinct last-7 `service_date`s with SYSTEM skips noting `cutoff_passed`. Threshold: **≥ 3** days.
2. **Meal-offs:** distinct last-7 `service_date`s with skip_source in `{customer, admin}`. Threshold: **≥ 5** days.
3. **Wallet below one-day cost:** spendable wallet balance (`wallet.balance`) **strictly less** than estimated one-day meal cost for the active subscription.

### One-day cost estimate

```
one_day ≈ meal.total_price / days_in_current_month
          × (preference_periods / package_periods)
          × quantity
```

- `preference_periods`: 2 if subscription `meal_period_snapshot=both`, else 1  
- `package_periods`: 2 if meal package `meal_period=both`, else 1  

Documented approximation when per-slot published prices are not available in set-based filters. Python helper: `estimate_one_day_meal_cost`.

## ORM usage (no full-table Python loops)

```python
from orders.services.customer_lifecycle import (
    annotate_lifecycle,
    filter_by_lifecycle,
    LIFECYCLE_UNSUBSCRIBED,
)

qs = annotate_lifecycle(CustomerProfile.objects.all())
unsubscribed = filter_by_lifecycle(
    CustomerProfile.objects.all(),
    LIFECYCLE_UNSUBSCRIBED,
)
```

## Examples

| Setup | Lifecycle |
|-------|-----------|
| New customer, never subscribed | `never_subscribed` |
| Cancelled only; no active | `unsubscribed` |
| Active + blocked 3+ of last 7 days | `at_risk` |
| Active + 5 meal-off days in last 7 | `at_risk` |
| Active + wallet < one-day cost | `at_risk` |
| Prior cancel then new active, healthy | `won_back` |
| Active, healthy, first subscription | `active` |
| Would be won_back but currently blocked ≥3 days | `at_risk` (precedence) |

## How to verify

```bash
python manage.py test orders.tests.test_customer_lifecycle -v2
```
