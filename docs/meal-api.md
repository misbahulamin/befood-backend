# Meal API

## Feature overview
This feature covers meal management for the Befood-Bachelors E-Food backend. The backend supports creating, listing, retrieving, updating, and soft-deleting meals.

The Django model is named `MealCategory`, but the API uses meal-focused naming in responses and documentation.

Public users can list and view active meals. Admin or outlet manager users can create, update, and soft-delete meals.

## Meal model fields

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `meal_name` | string | yes | Max length 255. Example: `Chicken Rice Bowl` |
| `total_price` | decimal | yes | Must be greater than 0. Example: `180.00` |
| `per_meal_price` | decimal | computed | `total_price / present_month_days`. Returned on list/detail responses only. Example: `88.29` |
| `meal_thumbnail` | image file | yes on create | Uploaded to `meals/thumbnails/` |
| `meal_type` | string choice | yes | Package duration/type |
| `description` | text | no | Optional description |
| `is_active` | boolean | no | Default `true` |
| `created_at` | datetime | auto | Set on create |
| `updated_at` | datetime | auto | Updated on save |

## Meal type naming convention

Use these API values exactly:

| Value | Display label |
| --- | --- |
| `daily` | Daily |
| `weekly` | Weekly |
| `half_monthly` | Half Monthly |
| `monthly` | Monthly |
| `six_months` | Six Months |
| `yearly` | Yearly |

Important:

- Do not use `1 month` as a database/API value. Use `monthly`.
- Do not use `6 monthly` as a database/API value. Use `six_months`.

## Per meal price calculation

List and detail responses include a computed field:

```text
per_meal_price = total_price / present_month_days
```

Where `present_month_days` is the number of days in the current calendar month at request time.

Example for a monthly package priced at `2737.00` BDT in a 31-day month:

```text
per_meal_price = 2737.00 / 31 = 88.29
```

The value is rounded to 2 decimal places.

## Thumbnail upload rule

Upload path:

```text
meals/thumbnails/
```

Filename format:

```text
meal-name-YYYYMMDD-HHMMSS.ext
```

Rules:

- Convert spaces to hyphens
- Use lowercase
- Remove unsafe filename characters
- Keep original file extension

Example:

```text
chicken-rice-bowl-20260710-153045.jpg
```

Allowed image extensions:

- `jpg`
- `jpeg`
- `png`
- `webp`

Maximum image size:

- `5MB`

## API endpoint list

Base prefix:

```text
/meals/
```

Endpoints:

- `GET /meals/` — list meals
- `GET /meals/<id>/` — meal detail
- `POST /meals/` — create meal
- `PATCH /meals/<id>/` — update meal
- `DELETE /meals/<id>/` — soft delete meal (`is_active=false`)

## Request examples

### Create meal

`POST /meals/`

Content-Type:

```text
multipart/form-data
```

Form fields:

```text
meal_name = Chicken Rice Bowl
total_price = 180.00
meal_thumbnail = image file
meal_type = daily
is_active = true
description = Healthy chicken rice bowl
```

Headers:

```text
Authorization: Token <MANAGER_OR_ADMIN_TOKEN>
```

### Update meal

`PATCH /meals/1/`

Content-Type:

```text
multipart/form-data
```

Example fields:

```text
meal_name = Updated Chicken Rice Bowl
total_price = 200.00
meal_type = weekly
is_active = true
```

If `meal_thumbnail` is included, the same filename rule is applied again.

### List meals with filters

```text
GET /meals/?meal_type=daily
GET /meals/?is_active=true
GET /meals/?search=chicken
```

## Response examples

### List / detail success

```json
{
  "id": 1,
  "meal_name": "Chicken Rice Bowl",
  "total_price": "180.00",
  "per_meal_price": "5.81",
  "meal_thumbnail": "http://127.0.0.1:8000/media/meals/thumbnails/chicken-rice-bowl-20260710-153045.jpg",
  "meal_type": "daily",
  "meal_type_display": "Daily",
  "is_active": true,
  "created_at": "2026-07-10T15:30:45+06:00",
  "updated_at": "2026-07-10T15:30:45+06:00"
}
```

Detail responses also include:

```json
{
  "description": "Healthy chicken rice bowl"
}
```

### Create success

Status: `201 Created`

Returns the created meal detail object.

### Soft delete success

Status: `204 No Content`

The meal remains in the database with `is_active=false`.

## Validation rules

- `meal_name` is required.
- `total_price` must be greater than 0.
- `meal_type` must be one of:
  - `daily`
  - `weekly`
  - `half_monthly`
  - `monthly`
  - `six_months`
  - `yearly`
- `meal_thumbnail` is required on create.
- Image extension must be `jpg`, `jpeg`, `png`, or `webp`.
- Image size must not exceed `5MB`.

## Error responses

### Validation error

Status: `400 Bad Request`

```json
{
  "total_price": ["Total price must be greater than 0."]
}
```

```json
{
  "meal_thumbnail": ["Meal thumbnail is required."]
}
```

```json
{
  "meal_type": ["Invalid meal type. Allowed values: daily, half_monthly, monthly, six_months, weekly, yearly."]
}
```

### Authentication required

Status: `401 Unauthorized`

Returned for create/update/delete when no valid token is provided.

### Permission denied

Status: `403 Forbidden`

Returned when the authenticated user is not in `ADMIN` or `OUTLET_MANAGER`.

### Not found

Status: `404 Not Found`

Returned when the meal id does not exist.

## Frontend implementation notes

### Form fields

- `meal_name`: text input
- `total_price`: number input
- `meal_thumbnail`: image upload input
- `meal_type`: dropdown
- `is_active`: checkbox or switch

### Meal type dropdown options

```json
[
  { "label": "Daily", "value": "daily" },
  { "label": "Weekly", "value": "weekly" },
  { "label": "Half Monthly", "value": "half_monthly" },
  { "label": "Monthly", "value": "monthly" },
  { "label": "Six Months", "value": "six_months" },
  { "label": "Yearly", "value": "yearly" }
]
```

### Frontend behavior

- Submit create/update requests as `multipart/form-data`.
- Image field name must be `meal_thumbnail`.
- Do not send image as base64.
- Show image preview before upload.
- Accept image types: `jpg`, `jpeg`, `png`, `webp`.
- Recommended max image size: `5MB`.
- Show backend validation errors clearly.
- Filter meals by `meal_type` when needed.
- Use the `meal_thumbnail` URL directly for image preview/display.
- Display `per_meal_price` as the daily cost estimate based on the current month's day count.

### Example frontend FormData

```javascript
const formData = new FormData();
formData.append('meal_name', 'Chicken Rice Bowl');
formData.append('total_price', '180.00');
formData.append('meal_thumbnail', fileInput.files[0]);
formData.append('meal_type', 'daily');
formData.append('is_active', 'true');
```

## Form-data upload instructions

1. Set request method to `POST` for create or `PATCH` for update.
2. Set header `Authorization: Token <token>` for manager/admin actions.
3. Do not manually set `Content-Type`; let the browser/client set the multipart boundary.
4. Attach the image file using field name `meal_thumbnail`.
5. Send numeric fields like `total_price` as form fields, not JSON body.

## Manual Postman test steps

### 1. List meals (public)

- Method: `GET`
- URL: `http://127.0.0.1:8000/meals/`
- Auth: none

### 2. Create meal (manager/admin)

- Method: `POST`
- URL: `http://127.0.0.1:8000/meals/`
- Auth: `Token <ADMIN_OR_OUTLET_MANAGER_TOKEN>`
- Body: `form-data`
- Fields:
  - `meal_name`: `Chicken Rice Bowl`
  - `total_price`: `180.00`
  - `meal_type`: `daily`
  - `is_active`: `true`
  - `meal_thumbnail`: choose a jpg/png/webp file under 5MB

Expected result:

- Status `201`
- Response includes `meal_thumbnail` absolute URL
- Response includes `meal_type_display`

### 3. Retrieve meal detail

- Method: `GET`
- URL: `http://127.0.0.1:8000/meals/<id>/`

### 4. Update meal

- Method: `PATCH`
- URL: `http://127.0.0.1:8000/meals/<id>/`
- Auth: manager/admin token
- Body: `form-data`
- Update any of:
  - `meal_name`
  - `total_price`
  - `meal_type`
  - `is_active`
  - `meal_thumbnail`

### 5. Filter meals

- `GET http://127.0.0.1:8000/meals/?meal_type=monthly`
- `GET http://127.0.0.1:8000/meals/?search=chicken`
- `GET http://127.0.0.1:8000/meals/?is_active=true`

### 6. Soft delete meal

- Method: `DELETE`
- URL: `http://127.0.0.1:8000/meals/<id>/`
- Auth: manager/admin token

Expected result:

- Status `204`
- Meal disappears from public list
- Record remains in admin/database with `is_active=false`

### 7. Validation checks

Try these to confirm validation:

- Create without `meal_thumbnail` → `400`
- Create with `total_price=0` → `400`
- Create with invalid `meal_type` → `400`
- Upload `.gif` image → `400`
- Upload image larger than 5MB → `400`

## Swagger/OpenAPI

Meal endpoints are documented under tag:

```text
Meal Management
```

Swagger UI:

```text
http://127.0.0.1:8000/api/docs/
```

## Notes

- Meals are not connected to cart, orders, or payments yet.
- Public list/detail endpoints only return active meals unless the authenticated user is admin/outlet manager.
- Delete is soft delete only.
