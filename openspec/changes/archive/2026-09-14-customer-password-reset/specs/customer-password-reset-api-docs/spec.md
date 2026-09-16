## ADDED Requirements

### Requirement: Backend customer password-reset technical docs
The system SHALL ship backend technical documentation at `user_management/docs/backend/customer-password-reset.md` that explains the complete customer password recovery feature for engineers who do not know the codebase. The document MUST include: plain-language summary, who uses the flow, mental model / security rules, auth/headers/base path, endpoint grid, permissions, models/services involved, business validation rules, full numbered workflow (request → email link → validate → confirm → login), request/response examples for every endpoint (success and errors), field meanings, HTTP status map, token lifetime notes, how to verify (Swagger + tests), and links to related auth docs.

#### Scenario: Backend docs cover full workflow order
- **WHEN** a backend or full-stack engineer reads `customer-password-reset.md`
- **THEN** the docs state which API to call first, what happens after each call, and that login is required after confirm

#### Scenario: Backend docs document all three endpoints
- **WHEN** a reader opens the backend password-reset docs
- **THEN** request, validate, and confirm endpoints each show method, path, body fields, success response, and error cases

### Requirement: Frontend and mobile password-reset integration docs
The system SHALL ship client integration documentation at `user_management/docs/frontend/customer-password-reset.md` so web and mobile developers can implement forgot-password without reading backend code. The document MUST include: summary, deep-link format from the email (`uid`/`token` query params), step-by-step UI flow, headers (`Content-Type`, optional `X-Client-Type`, no Authorization on reset endpoints), JSON examples for request/validate/confirm, recommended UX (generic check-email after request; disable submit until validate OK; clear errors for weak passwords), post-confirm redirect to login, note that prior tokens are invalidated, edge cases (expired link, reused link, unverified email still needs verification before login), and target clients (web + mobile).

#### Scenario: Frontend docs explain email deep link parsing
- **WHEN** a client developer implements the reset page
- **THEN** the docs show how to read `uid` and `token` from the email URL and POST them to validate/confirm

#### Scenario: Frontend docs forbid assuming auto-login
- **WHEN** a client developer finishes confirm successfully
- **THEN** the docs require navigating to login (or equivalent) rather than expecting an auth token in the confirm response

### Requirement: Related auth docs stay consistent
Existing branded-auth-emails and customer-auth overview docs MUST be updated so they no longer describe confirm-reset as missing/follow-up, and MUST link to the new password-reset docs.

#### Scenario: Branded email docs point to confirm API
- **WHEN** a reader opens the branded-auth-emails frontend or backend docs after this change
- **THEN** those docs reference the confirm (and validate) endpoints or the new password-reset doc instead of saying confirm is only a follow-up
