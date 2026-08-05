# Deferred Domain Public UUIDs

## Purpose
Define UUID-first requirements for deferred public domains before their client-facing endpoints are introduced.

## Requirements

### Requirement: Stub domains ship UUID-first

Before mounting customer- or partner-facing endpoints for `wallet`, `payments`, `delivery`, `promotions`, or `notifications`, each exposed model MUST include `public_id` and serializers/views MUST use UUID lookup. New public serializers MUST NOT expose sequential integer primary keys as the client identity.

#### Scenario: New wallet endpoint uses public_id

- **WHEN** a wallet resource API is first mounted for clients
- **THEN** list/detail identity uses `public_id` and lookup is by `public_id`

### Requirement: Readiness checklist before mounting

A deferred-domain feature MUST document in its frontend/backend docs: model `public_id`, URL shape, and that integer PK is internal-only.

#### Scenario: Docs required at mount time

- **WHEN** a stub app’s first public endpoint is released
- **THEN** its docs state UUID identity rules consistent with the public-uuid convention
