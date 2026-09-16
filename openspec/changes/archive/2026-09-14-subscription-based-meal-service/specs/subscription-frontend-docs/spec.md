## ADDED Requirements

### Requirement: Frontend documentation for customer subscription

The system SHALL include frontend developer documentation at `orders/docs/frontend/customer-meal-subscription.md` that describes how the customer app replaces monthly Order Now with subscribe / current status / cancel. The document MUST cover auth, endpoint grid, field meanings, wallet minimum UX, error codes (insufficient balance, frozen wallet, already subscribed, inactive plan), and recommended call order. It MUST be written for a reader who does not already know the feature.

#### Scenario: Customer doc present after implementation

- **WHEN** this change is implemented
- **THEN** `orders/docs/frontend/customer-meal-subscription.md` exists and maps Subscribe, Current, and Cancel screens to APIs

### Requirement: Frontend documentation for admin plans and subscribers

The system SHALL include frontend developer documentation at `orders/docs/frontend/admin-subscription-management.md` that describes Admin Panel subscription-plan CRUD and the subscriber list/detail board. The document MUST cover `IsVerifiedAdmin` auth, filters, progress fields, relationship to existing mark-delivered and meal-demand screens, and the minimum-wallet settings field used at subscribe time.

#### Scenario: Admin doc present after implementation

- **WHEN** this change is implemented
- **THEN** `orders/docs/frontend/admin-subscription-management.md` exists and maps plan management and subscriber list to APIs

### Requirement: Breaking monthly-order client migration is documented

Frontend docs MUST state that customer `POST` meal-order create, the orderable-months picker, and same-month repurchase are retired, and MUST name the replacement subscribe APIs and the stable error clients receive if they still call create.

#### Scenario: Migration notes for Order Now

- **WHEN** a frontend developer follows the subscription frontend docs
- **THEN** they can remove the month picker checkout and wire Subscribe without guessing deprecated order-create fields
