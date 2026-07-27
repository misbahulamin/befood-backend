# Admin Meal Ingredients & Recipes API

> **Superseded.** Meal costing is now **month-based meal cycle management** (servings per month, not kg recipes).
>
> Read the current guide: [`meals/docs/backend/meal-cycle-management.md`](../meals/docs/backend/meal-cycle-management.md)
>
> OpenSpec change: `openspec/changes/month-based-meal-cycle/`
>
> Legacy `/meals/recipes/` endpoints were removed. Use `/meals/cycles/`, `/meals/cycle-plans/`, and `/meals/cycle-plan-lines/` instead.

The sections below are historical notes for the previous Ingredient + MealRecipe (kg quantity) design and should not be used for new integrations.

---

# (Historical) Admin Meal Ingredients & Recipes API

## 1. Feature overview

This feature lets **verified admin users** manage:

- **Ingredients** — raw food items with purchase cost and serving capacity
- **Meal Recipes** — ingredient quantities required for each meal package/category over a 30-day cycle

These APIs are **admin-only**. Customers and public users cannot access them.

The recipe target uses the existing `MealCategory` model. API responses use meal-focused naming where helpful.

**Authentication:** Token auth (`Authorization: Token <token>`)

**Admin login:** Use `POST /user_management/admin/login/` first. See [admin-auth-api.md](./admin-auth-api.md).

**Base prefix:** `/meals/`

---

## 2. Business purpose

| Concept | Purpose |
| --- | --- |
| Ingredient | Master list of food items (Beef, Chicken, Rice, Dal, Egg, Potato) |
| `price_per_kg` | Purchase cost per kilogram |
| `customers_per_kg` | How many customers 1 kg can serve |
| `pieces_per_kg` | Optional piece count per kg (e.g. chicken pieces) |
| MealRecipe | Links a meal package to ingredients with cycle quantity |
| `quantity_in_cycle` | Total kg needed for one cycle (default 30 days) |

### Example

- 1 kg Rice serves 8 customers at BDT 60/kg
- Monthly Chicken Plan needs 15.5 kg chicken in 30 days
- Estimated cycle cost = `15.5 × 220 = 3410.00` BDT

For the current month-aware servings model, see the superseding guide linked at the top of this file.
