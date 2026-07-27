# Monthly Meal Menu Schedule

## 1. What is this?

After a **meal cycle plan** is finalized (how many times each ingredient is served in the month), admins build a **day-by-day calendar**: which date, lunch or dinner, which ingredients.

**Simple idea:**

1. Finalize a cycle plan for a package (Regular, Student, …) for a month.
2. Create a monthly menu schedule for that plan.
3. Assign ingredients to each `(date, lunch|dinner)` slot — never more than the plan’s `servings_count`.
4. Publish when every slot has exactly one **main** protein.
5. Kitchen uses the full month (admin only). Customers with an active order only see **today’s** menu after reveal times (default lunch 08:00, dinner 16:00, `Asia/Dhaka`).

**Who can use what:**

| Caller | Full month schedule | Reveal settings | Today menu |
| --- | --- | --- | --- |
| Verified admin | Yes | Yes | No (use admin schedule detail) |
| Verified customer | No | No | Yes (own active packages only) |
| Anonymous | No | No | No |

**Auth (admin):** `Authorization: Token <admin_token>`  
**Auth (customer):** `Authorization: Token <customer_token>` (email-verified `CUSTOMER`)

**Base path:** `/meals/`

---

## 2. Mental model

```
MealCycle (2026-07 → 31 days → 62 meals)
  └── MealCyclePlan (finalized) — Chicken × 20, Beef × 42, …
        └── MonthlyMenuSchedule (draft | published)
              └── MonthlyMenuSlot (date + lunch|dinner)
                    └── MonthlyMenuSlotItem (ingredient)
```

| Concept | Meaning |
| --- | --- |
| Quota | From cycle plan line `servings_count` — hard cap on schedule assignments |
| Slot | One calendar date + `lunch` or `dinner` |
| Main | At most one `product_role=main` per slot; publish requires every slot filled |
| Sync | Suggest copying another package’s calendar without exceeding this package’s quotas |
| Reveal | Clock times when today’s lunch/dinner become visible to customers |

---

## 3. Permissions

| Endpoint area | Permission |
| --- | --- |
| `/meals/menu-schedules/` | `IsVerifiedAdmin` |
| `/meals/menu-reveal-settings/` | `IsVerifiedAdmin` |
| `/meals/today-menu/` | `IsVerifiedCustomer` |

---

## 4. Endpoint grid

| Method | Endpoint | Why |
| --- | --- | --- |
| CRUD | `/meals/menu-schedules/` | Create/list/detail/patch notes/delete draft |
| `PUT` | `/meals/menu-schedules/{id}/assignments/` | Replace full-month matrix |
| `GET` | `/meals/menu-schedules/{id}/quota-summary/` | Planned / used / remaining / lunch·dinner counts |
| `POST` | `/meals/menu-schedules/{id}/publish/` | Lock for customers + kitchen published source |
| `POST` | `/meals/menu-schedules/{id}/unpublish/` | Back to draft for edits |
| `POST` | `/meals/menu-schedules/{id}/sync-suggestions/` | Suggest from another package schedule |
| `POST` | `/meals/menu-schedules/{id}/apply-sync/` | Apply suggestion (or explicit assignments) |
| `GET`/`PATCH` | `/meals/menu-reveal-settings/` | Lunch/dinner reveal clocks + timezone |
| `GET` | `/meals/today-menu/` | Customer today’s visible periods |

Swagger tags: **Admin Meal Menu Schedule**, **Customer Today Menu**.

---

## 5. Full admin workflow (call order)

```mermaid
sequenceDiagram
    participant Admin
    participant API

    Admin->>API: Finalize cycle plan (existing)
    Admin->>API: POST /meals/menu-schedules/ {plan_id}
    Admin->>API: PUT .../assignments/ (date + period + ingredients)
    Admin->>API: GET .../quota-summary/
    opt Cross-package
        Admin->>API: POST target/sync-suggestions/ {source_schedule_id}
        Admin->>API: POST target/apply-sync/ {source_schedule_id}
    end
    Admin->>API: POST .../publish/
    Note over Admin,API: Kitchen reads full schedule; customers use today-menu
```

### Step-by-step

1. Login as verified admin.
2. Ensure cycle plan for the package/month is **finalized**.
3. `POST /meals/menu-schedules/` with `plan_id`.
4. `PUT .../assignments/` with all slots you want to set (bulk replace).
5. Check `GET .../quota-summary/` — no `over_quota`, mains progressing toward full month.
6. Optionally sync another package from a source schedule.
7. `POST .../publish/` when every date×period has exactly one main.
8. Optionally `PATCH /meals/menu-reveal-settings/` for reveal clocks.
9. To edit again: `POST .../unpublish/` → edit → publish.
10. To reopen the **cycle plan**: unpublish/delete schedule first if published; draft schedule is **deleted** on reopen.

---

## 6. Request / response examples

### 6.1 Create schedule

`POST /meals/menu-schedules/`

```json
{
  "plan_id": 12,
  "notes": "July Regular kitchen calendar"
}
```

Success `201` (important fields):

```json
{
  "id": 1,
  "plan": 12,
  "cycle_year": 2026,
  "cycle_month": 7,
  "meal_category_name": "Regular Package",
  "status": "draft",
  "assignments": [],
  "quota_summary": [
    {
      "ingredient_id": 1,
      "ingredient_name": "Chicken",
      "product_role": "main",
      "planned": 20,
      "used": 0,
      "remaining": 20,
      "lunch_count": 0,
      "dinner_count": 0,
      "over_quota": false
    }
  ]
}
```

### 6.2 Bulk assignments

`PUT /meals/menu-schedules/1/assignments/`

```json
{
  "assignments": [
    {
      "service_date": "2026-07-22",
      "meal_period": "lunch",
      "ingredient_ids": [1, 3]
    },
    {
      "service_date": "2026-07-22",
      "meal_period": "dinner",
      "ingredient_ids": [2, 3]
    }
  ]
}
```

- `meal_period`: `lunch` | `dinner`
- Dates must fall in the cycle month
- Ingredients must exist on the linked cycle plan
- Counts must not exceed plan `servings_count`
- At most one `main` per slot

### 6.3 Sync suggestion + apply

`POST /meals/menu-schedules/2/sync-suggestions/`

```json
{ "source_schedule_id": 1 }
```

Response includes `assignments`, `unfilled_main_slots`, `remaining_quota`, `divergence_warnings`.

`POST /meals/menu-schedules/2/apply-sync/`

```json
{ "source_schedule_id": 1 }
```

Or pass explicit `assignments` (same shape as bulk PUT). Target must be **draft**.

Unequal quotas (Regular Chicken 12, Student Chicken 10): Student suggestion mirrors at most 10 Chicken slots.

### 6.4 Reveal settings

`GET /meals/menu-reveal-settings/`

```json
{
  "timezone": "Asia/Dhaka",
  "lunch_reveal_time": "08:00:00",
  "dinner_reveal_time": "16:00:00",
  "updated_at": "2026-07-22T12:00:00Z"
}
```

`PATCH /meals/menu-reveal-settings/`

```json
{
  "lunch_reveal_time": "07:30:00",
  "dinner_reveal_time": "15:30:00"
}
```

### 6.5 Customer today menu

`GET /meals/today-menu/`

Requires verified customer token and an **active non-cancelled order** covering today’s business-local date for that meal package. Schedule for that month must be **published**.

Example after lunch reveal, before dinner:

```json
{
  "service_date": "2026-07-22",
  "timezone": "Asia/Dhaka",
  "lunch_reveal_time": "08:00",
  "dinner_reveal_time": "16:00",
  "visible_periods": ["lunch"],
  "packages": [
    {
      "meal_category_id": 5,
      "meal_name": "Regular Package",
      "order_id": 99,
      "service_date": "2026-07-22",
      "schedule_published": true,
      "periods": [
        {
          "meal_period": "lunch",
          "ingredients": [
            { "id": 1, "name": "Chicken", "product_role": "main" },
            { "id": 3, "name": "Rice", "product_role": "staple" }
          ]
        }
      ]
    }
  ]
}
```

After dinner reveal, `visible_periods` is `["lunch", "dinner"]` and both period blocks are included.

---

## 7. Business validation rules

| Rule | When |
| --- | --- |
| Plan must be finalized | Create schedule |
| One schedule per plan | Create schedule |
| Ingredient on plan | Assign / sync apply |
| Used ≤ planned servings | Assign / sync apply |
| ≤ 1 main per slot | Assign / sync apply |
| Every slot has exactly 1 main | Publish |
| Non-mains may under-fill | Publish allowed |
| Published schedule blocks plan reopen | Reopen cycle plan |
| Draft schedule deleted on plan reopen | Reopen cycle plan |
| Published schedule not editable | Must unpublish first |

---

## 8. Errors (cheat sheet)

| Situation | Status | Notes |
| --- | --- | --- |
| Draft plan schedule create | 400 | `plan` message |
| Quota exceeded | 400 | `quota` |
| Two mains on one slot | 400 | `assignments` |
| Publish incomplete | 400 | `incomplete_slots` list |
| Reopen with published schedule | 400 | `menu_schedule` |
| Customer hits schedule APIs | 401/403 | Admin only |
| Today menu without auth | 401 | |
| Today menu no active order | 200 | `packages: []` |

---

## 9. How to verify

```bash
python manage.py test meals.tests.test_monthly_menu_schedule
```

Manual checklist (Swagger `/api/docs/`):

- [ ] Finalize a cycle plan
- [ ] Create menu schedule from that plan
- [ ] Reject schedule from draft plan
- [ ] PUT assignments; overflow rejected
- [ ] Publish fails until all mains filled; then succeeds
- [ ] Sync Student from Regular with unequal chicken quotas
- [ ] Customer without order sees empty packages
- [ ] Customer with order sees lunch only after 08:00, dinner after 16:00
- [ ] Reopen blocked while schedule published; draft schedule deleted on reopen

---

## 10. Related

- Cycle costing doc: [`meal-cycle-management.md`](./meal-cycle-management.md)
- OpenSpec change: `openspec/changes/monthly-meal-menu-schedule/`
