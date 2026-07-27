# Order API

## Feature overview

This feature lets a verified logged-in customer order one meal package from an existing active `MealCategory`.

The backend automatically calculates:

- `order_start_date`
- `order_end_date`
- `service_days_count`
- `order_month`

Snapshot fields are stored at order time so future meal price or name changes do not affect old orders.

Payment, wallet, delivery, rider assignment, notifications, and promotions are not connected in this version.

## Order business rules

1. Customer must be authenticated.
2. Customer must verify email before ordering.
3. Customer should belong to the `CUSTOMER` group.
4. Customer can order only active meal packages.
5. Within the same calendar month, a customer cannot order another non-cancelled meal package.
6. Customer can place a new order in the same month only if the previous order was cancelled.
7. Default order status is `confirmed` because payment is not implemented yet.
8. One meal package per order.

## Meal type duration calculation

Duration is calculated from the selected meal's `meal_type` at order time.

Reference date defaults to today's local date unless noted otherwise.

| meal_type | start_date | end_date | service_days_count |
| --- | --- | --- | --- |
| `daily` | today | today | 1 |
| `weekly` | today | today + 6 days | 7 |
| `half_monthly` | today | today + 14 days | 15 |
| `monthly` | first day of current calendar month | last day of current calendar month | total days in current month |
| `six_months` | today | today + 6 calendar months - 1 day | inclusive days between start and end |
| `yearly` | today | today + 1 calendar year - 1 day | inclusive days between start and end |

Examples:

- Monthly order on `2026-07-10` → start `2026-07-01`, end `2026-07-31`, service days `31`
- Monthly order in February `2028` → service days `29`
- Six months from `2026-01-31` → end `2026-07-30`

`order_month` is always calculated as `YYYY-MM` from `order_start_date`.

Example:

- start date `2026-07-01` → `order_month = 2026-07`

## Month lock rule

Within the same `order_month`, a customer cannot have more than one non-cancelled meal package order.

Blocked statuses:

- `pending`
- `confirmed`
- `active`
- `completed`

Allowed replacement:

- If the existing order is `cancelled`, the customer may place a new order in the same month.

Backend error message:

```text
You already have a meal package for this month. You cannot change meal type within the same month.
```

Example:

- Customer orders Monthly package in July 2026.
- Until July 2026 ends, the customer cannot order Daily/Weekly/Half Monthly/etc. in the same month unless the July order is cancelled.
- Customer can order again in August 2026.

## Order model fields

| Field | Type | Notes |
| --- | --- | --- |
| `customer` | FK | Links to `CustomerProfile` |
| `meal` | FK | Links to `MealCategory` |
| `meal_name_snapshot` | string | Meal name at order time |
| `meal_type_snapshot` | string | Meal type at order time |
| `total_price_snapshot` | decimal | Total price at order time |
| `per_meal_price_snapshot` | decimal | Per meal price at order time |
| `order_status` | string | `pending`, `confirmed`, `active`, `completed`, `cancelled` |
| `order_start_date` | date | Auto calculated |
| `order_end_date` | date | Auto calculated |
| `service_days_count` | integer | Auto calculated |
| `order_month` | string | Format `YYYY-MM` |
| `customer_note` | text | Optional note from customer |
| `created_at` | datetime | Auto |
| `updated_at` | datetime | Auto |

## API endpoint list

Base prefix:

```text
/orders/
```

Authentication header for protected endpoints:

```text
Authorization: Token <token>
```

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/orders/` | Create meal order |
| GET | `/orders/my-orders/` | List logged-in customer's orders |
| GET | `/orders/<id>/` | Order detail |
| POST | `/orders/<id>/cancel/` | Cancel order |
| GET | `/orders/current-package/` | Current month package |

Swagger UI:

```text
/api/docs/
```

Tag:

```text
Order Management
```

## Request examples

### Create order

```http
POST /orders/
Authorization: Token <token>
Content-Type: application/json
```

```json
{
  "meal_id": 1,
  "customer_note": "Please deliver after 1 PM"
}
```

### My orders

```http
GET /orders/my-orders/?order_status=confirmed&order_month=2026-07&meal_type=monthly
Authorization: Token <token>
```

### Order detail

```http
GET /orders/5/
Authorization: Token <token>
```

### Cancel order

```http
POST /orders/5/cancel/
Authorization: Token <token>
Content-Type: application/json
```

```json
{
  "note": "Changed my plan"
}
```

### Current package

```http
GET /orders/current-package/
Authorization: Token <token>
```

## Response examples

### Create order success

```json
{
  "id": 5,
  "meal": 1,
  "meal_name_snapshot": "Monthly Package",
  "meal_type_snapshot": "monthly",
  "meal_type_display": "Monthly",
  "total_price_snapshot": "2737.00",
  "per_meal_price_snapshot": "44.14",
  "order_status": "confirmed",
  "order_status_display": "Confirmed",
  "order_start_date": "2026-07-01",
  "order_end_date": "2026-07-31",
  "service_days_count": 31,
  "order_month": "2026-07",
  "customer_note": "Please deliver after 1 PM",
  "created_at": "2026-07-10T08:00:00Z",
  "updated_at": "2026-07-10T08:00:00Z",
  "customer": 1
}
```

### Current package when none exists

```json
{
  "current_package": null,
  "message": "No active meal package found for this month."
}
```

### Current package when order exists

```json
{
  "current_package": {
    "id": 5,
    "meal_name_snapshot": "Monthly Package",
    "meal_type_snapshot": "monthly",
    "order_status": "confirmed",
    "order_month": "2026-07"
  },
  "message": null
}
```

## Error responses

### Unauthenticated

```json
{
  "detail": "Authentication credentials were not provided."
}
```

Status: `401`

### Unverified customer

Status: `403`

Message indicates email verification is required.

### Inactive meal

```json
{
  "meal_id": [
    "This meal package is not available for ordering."
  ]
}
```

Status: `400`

### Month lock

```json
{
  "non_field_errors": [
    "You already have a meal package for this month. You cannot change meal type within the same month."
  ]
}
```

Status: `400`

### Cancel not allowed

```json
{
  "order_status": [
    "Only pending or confirmed orders can be cancelled."
  ]
}
```

or

```json
{
  "order_start_date": [
    "Order can only be cancelled on or before the start date."
  ]
}
```

Status: `400`

## Frontend implementation notes

### Frontend order flow

1. User must login first.
2. User must verify email first.
3. On `/menu` page, each meal card has `Select` or `Order Now` button.
4. Before placing order, frontend can call:

```http
GET /orders/current-package/
```

5. If `current_package` exists, show:

```text
আপনার এই মাসে ইতোমধ্যে একটি মিল প্যাকেজ চালু আছে। এই মাসে প্যাকেজ পরিবর্তন করা যাবে না।
```

6. When user clicks order, frontend sends:

```http
POST /orders/
```

```json
{
  "meal_id": 1,
  "customer_note": ""
}
```

7. If backend returns month lock error, show the same Bangla message.
8. After successful order, redirect to my orders page.
9. My orders page should call:

```http
GET /orders/my-orders/
```

10. Order detail page should call:

```http
GET /orders/<id>/
```

11. Cancel button should call:

```http
POST /orders/<id>/cancel/
```

### Frontend display fields

Show these order fields in UI:

- `meal_name_snapshot`
- `meal_type_snapshot`
- `total_price_snapshot`
- `per_meal_price_snapshot`
- `order_status`
- `order_start_date`
- `order_end_date`
- `service_days_count`
- `order_month`

## Manual Postman test steps

### 1. Register and verify customer

1. `POST /user_management/customer/register/`
2. Verify email using the link sent by email or test helper flow
3. `POST /user_management/login/`
4. Copy the returned token

### 2. List active meals

1. `GET /meals/?is_active=true`
2. Choose a meal id, for example `1`

### 3. Check current package before ordering

1. `GET /orders/current-package/`
2. Header: `Authorization: Token <token>`

### 4. Create order

1. `POST /orders/`
2. Header: `Authorization: Token <token>`
3. Body:

```json
{
  "meal_id": 1,
  "customer_note": "Please deliver after 1 PM"
}
```

4. Confirm response includes snapshot fields and calculated dates

### 5. Try second order in same month

1. Choose another meal id
2. Send another `POST /orders/`
3. Expect month lock error

### 6. List my orders

1. `GET /orders/my-orders/`
2. Optional filters:
   - `order_status=confirmed`
   - `order_month=2026-07`
   - `meal_type=monthly`

### 7. View order detail

1. `GET /orders/<id>/`

### 8. Cancel order

1. `POST /orders/<id>/cancel/`
2. Body optional:

```json
{
  "note": "Changed plan"
}
```

### 9. Create new order after cancel

1. Repeat create order request
2. Expect success if previous order was cancelled

### 10. Negative tests

1. Create order without token → expect `401`
2. Create order with unverified account → expect `403`
3. Create order with inactive meal id → expect `400`
4. Access another customer's order detail → expect `404`
