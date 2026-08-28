## 1. Branding assets and shared context

- [x] 1.1 Add Befood logo asset under `static/emails/` (or document `EMAIL_LOGO_URL`) and settings for logo URL, Play Store URL, social/contact constants, and password-reset frontend path
- [x] 1.2 Create `user_management/services/email_branding.py` with brand colors, footer links, greeting helper (`bhaiya` / `apu` / `bhaiya/apu`), and shared template context builder

## 2. Shared email templates

- [x] 2.1 Create `templates/emails/base_branded_email.html` (table layout, inline CSS, logo header, yellow brand highlight, Deep Ink CTA, Warm White surface, security block, Phitron-style footer with socials + Play Store badge + contact/address)
- [x] 2.2 Create shared plain-text footer include/partial for multipart text emails
- [x] 2.3 Redesign `customer_activation_email.html` / `.txt` / subject to extend shared shell: welcome copy, **Verify Email Address** button only (no OTP boxes), expiry + ignore-if-not-you notes
- [x] 2.4 Add `customer_password_reset_email.html` / `.txt` / subject with same shell: reset copy + **Reset Password** CTA

## 3. Wire activation send path

- [x] 3.1 Update `send_activation_email` to use branding context (greeting, logo, footer) while keeping existing uid/token activation link and 24h behavior
- [x] 3.2 Confirm resend-verification continues to use the updated activation templates

## 4. Password-reset email system

- [x] 4.1 Implement `send_password_reset_email` with Django `PasswordResetTokenGenerator`, frontend reset URL, and branded templates
- [x] 4.2 Add `POST` password-reset request API (anti-enumeration generic success) + URL + OpenAPI notes
- [x] 4.3 Ensure activation verify endpoint rejects password-reset tokens

## 5. Test send management command

- [x] 5.1 Add management command `send_test_auth_email` with `--type activation|password_reset` and `--to` (default `misbahul.amin.ai@gmail.com`)
- [x] 5.2 Document command usage in a short backend note under `user_management/docs/backend/` if project docs rules apply

## 6. Automated tests

- [x] 6.1 Unit-test greeting helper for male / female / unknown gender and missing first name
- [x] 6.2 Assert activation email HTML contains logo URL, Verify CTA, Play Store link, and does **not** contain verification-code digit UI
- [x] 6.3 Assert password-reset request: existing user triggers mail; unknown email returns generic success without mail
- [x] 6.4 Assert activation verify rejects a password-reset token
- [x] 6.5 Update any existing customer auth tests that assert old plain activation body copy

## 7. Manual / live QA checklist

- [ ] 7.1 Run `send_test_auth_email --type activation --to misbahul.amin.ai@gmail.com` via configured SMTP and confirm inbox rendering (logo, colors, button, footer)
- [ ] 7.2 Run `send_test_auth_email --type password_reset --to misbahul.amin.ai@gmail.com` and confirm same layout with Reset CTA
- [ ] 7.3 Spot-check in at least one webmail client (Gmail) for broken images, button clickability, and mobile width
- [ ] 7.4 Optionally register a throwaway account and confirm real registration path sends the new template
