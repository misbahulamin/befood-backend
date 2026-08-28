## Context

Customer activation mail today is a minimal HTML body (`templates/emails/customer_activation_email.html`) with no logo, no brand colors, and no footer. Copy is English-only and greets with `first_name` only. Password-reset email templates and send helpers do not exist yet; registration still uses `send_activation_email` + 24h link tokens.

Reference UX (provided screenshots): centered StackLearner-style verification email (headline, short body, primary CTA button, security note) plus Phitron-style brand footer (highlighted brand name, social icons, site/phone/address, store badges). Adapt to Befood — **omit OTP digit boxes**; primary CTA only.

Constraints: email clients need table-based layout, inline CSS, absolute HTTPS image URLs; SMTP is already configured via Django settings; `FRONTEND_URL` is available for deep links.

## Goals / Non-Goals

**Goals:**

- Shared branded shell for customer auth emails (activation + password reset).
- Befood palette: yellow `#FFD100` dominant accents, Deep Ink `#1C1A17` for text/CTA/icons, Warm White `#FDFCF8` for card/surface.
- Logo at top; primary button only (Verify Email Address / Reset Password); gender-aware Bangla honorific greeting.
- Footer: Facebook, Instagram, WhatsApp, site, phone, address, Google Play badge.
- Plain-text multipart alternative with equivalent information.
- Testable send path to `misbahul.amin.ai@gmail.com`.

**Non-Goals:**

- Redesigning deliveryman approval/rejection emails in this change (optional follow-up).
- OTP / six-digit verification code UI or SMS.
- Changing activation token algorithm, expiry (24h), or verify/resend API contracts.
- Building a full frontend reset-password page (backend supplies link to `FRONTEND_URL` path).
- Localization framework beyond Bangla honorifics + English/Bangla mix copy agreed for these two templates.

## Decisions

### 1. Shared base template + thin content templates

**Choice:** `templates/emails/base_branded_email.html` (and matching text partials/includes) with blocks for `preheader`, `headline`, `body`, `cta_label`, `cta_url`, `extra_note`. Activation and password-reset templates extend the base.

**Why:** One layout to maintain; both emails stay visually identical except copy/CTA.

**Alternatives:** Duplicate full HTML per email (rejected — drift risk); React/MJML build step (rejected — no existing email build pipeline).

### 2. Brand constants in one Python helper

**Choice:** Small helper (e.g. `user_management/services/email_branding.py`) that builds shared template context: brand colors, logo absolute URL, social/contact links, Play Store URL, greeting string, recipient email.

**Why:** Keeps `send_activation_email` / `send_password_reset_email` thin and testable without hardcoding URLs in every template.

### 3. Greeting honorific from `CustomerProfile.gender`

**Choice:**

| Gender | Greeting |
|--------|----------|
| `male` | `Hello {display_name} bhaiya` |
| `female` | `Hello {display_name} apu` |
| missing / other | `Hello bhaiya/apu` |

`display_name` = `user.first_name` if present; otherwise omit name and use `Hello bhaiya` / `Hello apu` / `Hello bhaiya/apu` accordingly. At registration, gender and name are often empty → default `Hello bhaiya/apu`.

**Why:** Matches product voice; safe when onboarding incomplete.

### 4. No verification code boxes

**Choice:** Activation email shows only **Verify Email Address** button linking to existing `activation_link`. Password-reset shows **Reset Password** linking to frontend reset URL with uid/token query or path.

**Why:** Product request; current backend is link-based, not OTP.

### 5. Logo hosting

**Choice:** Host logo under project static (e.g. `static/emails/befood-logo.png`) and expose absolute URL via `settings` (`EMAIL_LOGO_URL` or `{FRONTEND_URL}/...` / media CDN). Template uses `<img src="{{ logo_url }}">` at top, centered.

**Why:** Email clients block relative URLs. Exact asset file may be supplied during apply; placeholder path documented in tasks.

### 6. Typography

**Choice:** Web-safe stack matching the reference feel: `'Segoe UI', Tahoma, Geneva, Verdana, sans-serif` for body/headings; optional cursive for tagline only (`'Segoe Script', 'Comic Sans MS', cursive`) with graceful fallback — email-safe, close to screenshot aesthetic without webfont loading failures.

**Why:** Most clients strip remote `@font-face`.

### 7. Password-reset email + send helper; thin API if absent

**Choice:** Add `send_password_reset_email` using Django’s `PasswordResetTokenGenerator` (or project-equivalent), templates, and a minimal `POST` forgot-password endpoint with anti-enumeration if none exists. Reset link targets `FRONTEND_URL` password-reset route with `uid` + `token`.

**Why:** Templates alone are not a “system”; send path needed for real test mail. Full confirm-reset API can reuse Django patterns in the same change if required for end-to-end test.

### 8. Footer / contact constants (product-provided)

| Field | Value |
|-------|--------|
| Site | https://befood.com.bd |
| Phone / WhatsApp | +880 1751-678409 |
| Facebook | https://www.facebook.com/befoodbd |
| Instagram | https://instagram.com/befoodbd |
| Play Store | https://play.google.com/store/apps/details?id=bd.com.befood |
| Address | K.B Aman Ali Road, Boro Mia Masjid Goli, Bakolia., Chittagong, Bangladesh, 4203 |
| Tagline | Homestyle meals, every day — ঘরের স্বাদের খাবার |

Yellow highlight behind the word **Befood** in headlines/footer (inline `background-color:#FFD100`).

### 9. Manual test send

**Choice:** Management command `send_test_auth_email` with `--type activation|password_reset` and `--to` (default `misbahul.amin.ai@gmail.com`) that renders templates with sample context and sends via configured SMTP.

**Why:** Verifies real client rendering without full register/forgot flow every time.

## Risks / Trade-offs

- [Email clients strip CSS / block images] → Use table layout + inline styles; logo `alt="Befood"`; meaningful plain-text part.
- [Logo 404 if static URL wrong in prod] → Configurable `EMAIL_LOGO_URL`; verify in test send checklist.
- [Gender missing at signup] → Default `Hello bhaiya/apu` (accepted product rule).
- [Password-reset frontend path not finalized] → Use configurable `PASSWORD_RESET_FRONTEND_PATH` (e.g. `/reset-password`) documented in settings.
- [SMTP failure during test] → Command surfaces Django mail exceptions; do not fail unit tests on live SMTP.

## Migration Plan

1. Ship shared base + new templates; wire activation send to new context.
2. Add password-reset send (+ endpoint if needed).
3. Deploy static logo / set `EMAIL_LOGO_URL`.
4. Run unit tests + management-command send to test inbox.
5. Rollback: revert template/service commits; no DB migration expected unless settings-only.

## Open Questions

- Exact frontend password-reset URL path (default `/reset-password` unless product confirms).
- Final logo PNG asset source (design team vs existing marketing asset) — apply step will add file under `static/emails/`.
