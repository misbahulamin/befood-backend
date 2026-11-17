# Guest Meal Profit Reconciliation — Dry Run

**Command:** `python manage.py reconcile_guest_meal_profit`  
**Mode:** dry-run (no writes)  
**When:** 2026-11-16 (local)

## Result

Delivered guest orders missing profit rows: **1**

| public_id | service_date | meal_period | qty | total_amount |
|---|---|---|---:|---:|
| `779daefc-f995-4cbb-a7b8-b3e410c78fbc` | 2026-11-16 | dinner | 2 | 140.00 |

Matches the Admin Guest Meals screenshot case (Misbahul Amin / Dinner / qty 2 / ৳140 / Delivered).

## Next step (requires explicit approval for production)

```bash
python manage.py reconcile_guest_meal_profit --apply
```

Local verification may use `--apply` on the developer SQLite DB only.
