## ADDED Requirements

### Requirement: Activation email links use the frontend website origin
The system SHALL generate customer email verification (activation) links using the configured `FRONTEND_URL` base and a configurable frontend path (default `/verify-email`), producing an absolute URL of the form `{FRONTEND_URL}/verify-email/{uidb64}/{token}/` (trailing slash allowed). The system MUST NOT use the HTTP request host or Django absolute URI of the API verify route as the email href. The system MUST NOT include API hostnames such as `api.befood.com.bd` in activation email links when `FRONTEND_URL` is set to the public website. Token generation and the public API verify endpoint MUST remain unchanged.

#### Scenario: Registration activation email points at frontend SPA path
- **WHEN** a customer registers or requests resend verification and an activation email is sent
- **THEN** the email `activation_link` starts with `FRONTEND_URL`, contains the configured verification path and the same uid/token values used by the API, and does not use the API request host as the link origin

#### Scenario: Activation API endpoint remains available for the SPA
- **WHEN** a client calls `GET /user_management/verify-email/<uidb64>/<token>/` with a valid activation token
- **THEN** verification succeeds as before (account activated / email marked verified per existing rules)

#### Scenario: Invalid or expired token behavior unchanged
- **WHEN** a client calls the verify-email API with an invalid or expired token
- **THEN** the system rejects the request with the existing error contract

### Requirement: Delivery Man activation email links use the frontend website origin
The system SHALL generate Delivery Man email verification links using `FRONTEND_URL` and a configurable frontend path (default `/deliveryman/verify-email`), producing `{FRONTEND_URL}/deliveryman/verify-email/{uidb64}/{token}/`. The system MUST NOT embed the API absolute URI of `deliveryman-verify-email` in the email. The Delivery Man verify API endpoint and token rules MUST remain unchanged.

#### Scenario: Deliveryman registration email uses frontend deep link
- **WHEN** a Delivery Man registers and an activation email is sent
- **THEN** the email activation link uses `FRONTEND_URL` and the deliveryman SPA verify path with uid and token, not the API host

### Requirement: Environment-based frontend base URL
The system SHALL resolve the website origin for activation links from configuration (`FRONTEND_URL`), and SHALL resolve SPA path segments from configuration with documented defaults matching the customer and deliveryman frontend routes. Implementation MUST avoid hardcoding a single production domain in link-builder code beyond reading settings/env defaults consistent with the rest of the project.

#### Scenario: Override FRONTEND_URL in tests or staging
- **WHEN** `FRONTEND_URL` is set to a non-production origin (e.g. `http://localhost:5173`)
- **THEN** newly generated activation links use that origin as the scheme/host prefix
