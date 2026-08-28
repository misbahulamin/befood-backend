## Why

Customer registration activation emails are plain, unbranded HTML that do not match Befood’s visual identity. There is also no professional forgot-password email experience. First-touch emails should look trustworthy and on-brand so customers verify accounts and recover access confidently.

## What Changes

- Replace the customer registration/activation HTML (and plain-text) email with a modern, centered, StackLearner-style layout adapted to Befood branding (logo on top, yellow highlight accents, Deep Ink CTA button — **no OTP/code digit boxes**).
- Add a forgot-password / password-reset email using the **same shared layout**, with Befood-relevant copy and a primary **Reset Password** / equivalent CTA button.
- Introduce a shared email base (header logo, gender-aware Bangla greeting, body, CTA, security footer, brand footer with socials + Play Store + contact).
- Greeting rules: `Hello {name} bhaiya` / `Hello {name} apu` from profile gender; if gender unknown, `Hello bhaiya/apu`.
- Brand colors: Main Yellow `#FFD100` (dominant accents), Deep Ink `#1C1A17` (text/icons/buttons), Warm White `#FDFCF8` (surface/card areas only).
- Footer content: Facebook, Instagram, WhatsApp, site, phone, address, Google Play badge linking to `https://play.google.com/store/apps/details?id=bd.com.befood`.
- Keep existing activation token/link behavior (24h link verify); do **not** add a visible verification code UI.
- Add a repeatable test plan including a real send to `misbahul.amin.ai@gmail.com`.

## Capabilities

### New Capabilities
- `branded-auth-emails`: Shared Befood-branded HTML/text email shell and customer activation + password-reset email content, greeting rules, footer/contact/Play Store requirements, and send-context contracts.
- `customer-password-reset-email`: Password-reset email send helper (and minimal request flow if missing) that uses the shared branded template and secure reset link.

### Modified Capabilities
- (none — activation API/token behavior stays; only email presentation and new password-reset email capability are added)

## Impact

- Templates under `templates/emails/` (shared base + `customer_activation_*` + new password-reset templates).
- `user_management/services/email_verification.py` (and/or a small email branding helper) for greeting context, logo URL, brand constants, and password-reset send.
- Static or absolute public logo URL usable by email clients.
- Existing customer auth tests that assert email content; new template/context tests; manual SMTP test send.
- Out of scope unless needed for the test send: deliveryman email redesign, OTP-based verification, frontend UI for reset forms beyond the link target.
