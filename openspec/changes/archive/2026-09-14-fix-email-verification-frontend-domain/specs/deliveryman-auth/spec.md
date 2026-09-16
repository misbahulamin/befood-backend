## MODIFIED Requirements

### Requirement: Delivery Man must verify email before admin review
The system SHALL provide a Delivery Man–specific email verification **API** endpoint using a secure uid/token. Verification emails MUST deep-link to the frontend SPA path under `FRONTEND_URL` (default `/deliveryman/verify-email/{uidb64}/{token}/`); the SPA then calls the API. On successful API verification the system MUST set `is_email_verified=True` and `email_verified_at`, and MUST NOT grant login access until admin approval (`is_active` remains false and `is_verified` remains false). Already-verified links MUST return a clear already-verified message. Invalid or expired tokens MUST be rejected. Activation email hrefs MUST NOT use the API request host.

#### Scenario: Successful email verification queues admin review
- **WHEN** a registered Delivery Man opens a valid verification link before expiry (via frontend deep link that invokes the verify API)
- **THEN** the system marks the profile email as verified, keeps the account unapproved and inactive for login, and the account becomes eligible for the admin pending queue

#### Scenario: Invalid verification link
- **WHEN** a client uses an invalid or expired Delivery Man verification token
- **THEN** the system responds `400` with an invalid-or-expired message and does not change verification state

#### Scenario: Resend verification email
- **WHEN** an unverified Delivery Man requests resend verification for their email
- **THEN** the system sends a new verification email whose activation link uses `FRONTEND_URL` (not the API host), without revealing whether non-Delivery-Man emails exist beyond safe generic messaging consistent with customer resend behavior
