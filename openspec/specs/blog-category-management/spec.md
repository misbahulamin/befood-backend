## Purpose

Verified-admin REST management of blog categories used to group articles and drive related-article matching.

## Requirements

### Requirement: Admin blog category CRUD

The system SHALL expose a token-authenticated admin HTTP API for blog categories under `/blogs/categories/` using `IsVerifiedAdmin`. Verified admins MUST be able to create, list, retrieve, partially update, and delete blog categories identified by `public_id`. Each category MUST have a non-blank `name`, a unique `slug` (auto-generated from name when omitted on create), a `sort_order` integer (default `0`), and an `is_active` boolean (default `true`). Responses MUST include `public_id` and MUST NOT expose operations to anonymous users or non-admin authenticated users. Unverified admins MUST be denied.

#### Scenario: Verified admin creates category
- **WHEN** a verified admin `POST`s a valid category payload to `/blogs/categories/`
- **THEN** the system returns `201 Created` with `public_id`, `name`, `slug`, `sort_order`, and `is_active`

#### Scenario: Duplicate name rejected
- **WHEN** a verified admin creates a category whose `name` already exists
- **THEN** the system rejects the request with a validation error

#### Scenario: Non-admin denied
- **WHEN** an anonymous user or non-verified-admin authenticated user calls category admin endpoints
- **THEN** the system responds `401` or `403` as appropriate

### Requirement: Category delete nullifies article links

When a category is deleted, articles that referenced it MUST have their `category` set to null (SET_NULL). The delete MUST succeed even when articles still reference the category.

#### Scenario: Delete category with articles
- **WHEN** a verified admin deletes a category that still has articles
- **THEN** the system deletes the category and those articles have `category` cleared (null)

### Requirement: Admin category documentation

The change MUST ship frontend-facing documentation describing category admin endpoints, auth, fields, and the recommended workflow of creating categories before assigning them to articles.

#### Scenario: Frontend admin category doc present
- **WHEN** the change is implemented
- **THEN** `blogs/docs/frontend/blog-admin.md` documents category CRUD with examples
