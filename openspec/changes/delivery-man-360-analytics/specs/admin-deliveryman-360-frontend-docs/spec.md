## ADDED Requirements

### Requirement: Frontend documents Delivery Man 360 navigation
The system SHALL document (in `user_management` or `delivery_zones` frontend docs as appropriate) the Admin Panel navigation: **Delivery Men** list → select Delivery Man → **Delivery Man Profile / 360 Analytics Dashboard**. Documentation MUST state that analytics APIs are verified-admin only and identify riders by `public_id`.

#### Scenario: Docs describe list to dashboard path
- **WHEN** a frontend engineer reads the Delivery Man 360 frontend documentation
- **THEN** the docs describe the Delivery Men list, selection of a rider, and the 360 analytics dashboard entry

### Requirement: Frontend documents dashboard sections and API mapping
The documentation MUST map UI sections to backend endpoints and key fields:

| UI section | Primary API | Notes |
|------------|-------------|-------|
| Overview card | `GET /api/v1/web/delivery-men/{public_id}/` | name, phone, zone, joining date, status, availability |
| Today / Month / Lifetime | same overview metrics objects | lunch/dinner/total; lifetime customers & zones |
| Delivery history | `GET .../deliveries/` | lazy tab; pagination + filters |
| Activity timeline | `GET .../timeline/` | chronological events |
| Route map | `GET .../route/` | sequence + coordinates; map rendered client-side |
| Ranking / comparison | `GET .../rankings/` | optional list or compare view |

Overview MUST load without fetching full history. History, timeline, and route MUST be lazy-loaded.

#### Scenario: Docs require lazy history
- **WHEN** the frontend docs describe the dashboard data-loading strategy
- **THEN** they state that history, timeline, and route are loaded on demand and not embedded in the overview response

### Requirement: Frontend documents filters and empty states
The documentation MUST list allowlisted filters (date presets / range, meal type, zone, status) and empty-state copy guidance when a rider has no deliveries in range, no zone assignment, or no timeline events yet (Phase A).

#### Scenario: Docs cover empty timeline
- **WHEN** a rider has only mark-delivered events without intermediate logistics steps
- **THEN** the docs instruct the UI to show available delivered events and not treat missing pick/accept events as an error
