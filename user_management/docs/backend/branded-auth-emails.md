# Branded auth emails (backend)

## Quick summary

Customer **activation** and **password-reset** emails use a shared Befood-branded HTML/text shell (logo, gender-aware greeting, Deep Ink CTA, yellow accents, social/Play Store footer). No OTP digit boxes — link/button only.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | `/user_management/customer/register/` | Public | Creates account + sends branded activation email |
| POST | `/user_management/resend-verification/` | Public | Resends branded activation email |
| GET | `/user_management/verify-email/<uidb64>/<token>/` | Public | Activates account (activation token only) |
| POST | `/user_management/password-reset/` | Public | Requests branded password-reset email (anti-enumeration) |

## Branding settings

| Setting | Purpose |
|---------|---------|
| `EMAIL_LOGO_URL` | Absolute public S3/CDN logo URL (not AWS Console) |
| `EMAIL_FACEBOOK_ICON_URL` / `EMAIL_INSTAGRAM_ICON_URL` / `EMAIL_WHATSAPP_ICON_URL` | Black/yellow social icon images |
| `EMAIL_PLAY_STORE_URL` | Google Play listing |
| `EMAIL_PLAY_STORE_BADGE_URL` | Play badge image |
| `EMAIL_SITE_URL` / `EMAIL_PHONE` / `EMAIL_WHATSAPP` / `EMAIL_FACEBOOK_URL` / `EMAIL_INSTAGRAM_URL` / `EMAIL_ADDRESS` | Footer contact |
| `PASSWORD_RESET_FRONTEND_PATH` | Frontend path for reset CTA (default `/reset-password`) |
| `FRONTEND_URL` | Base URL for reset link |

Logo default:
`https://befood-media-storage.s3.ap-south-1.amazonaws.com/logo/befood_logo_for_template.png`

Do **not** use AWS Console page URLs as `EMAIL_LOGO_URL`. Brand name text must not use yellow highlighter backgrounds. Auth emails do not include a “Best Regards / The Befood Team” sign-off.

## Greeting rules

| Gender | With name | Without name |
|--------|-----------|---------------|
| `male` | `Hello {name} bhaiya` | `Hello bhaiya` |
| `female` | `Hello {name} apu` | `Hello apu` |
| unknown | `Hello {name} bhaiya/apu` | `Hello bhaiya/apu` |

## Password-reset request

**Request**

```http
POST /user_management/password-reset/
Content-Type: application/json

{ "email": "customer@example.com" }
```

**Response (always same shape)**

```json
{
  "message": "If an account exists for this email, password reset instructions will be sent."
}
```

Reset CTA opens `{FRONTEND_URL}{PASSWORD_RESET_FRONTEND_PATH}?uid=...&token=...`.

Activation verify **rejects** password-reset tokens (different token generators).

## Test send command

```bash
python manage.py send_test_auth_email --type activation --to misbahul.amin.ai@gmail.com
python manage.py send_test_auth_email --type password_reset --to misbahul.amin.ai@gmail.com
```

Options: `--first-name`, `--gender male|female|` (empty = unknown).

Requires working SMTP (`EMAIL_HOST_*` / `DEFAULT_FROM_EMAIL` in env).

## How to verify

1. Unit tests: `python manage.py test user_management.tests.test_branded_auth_emails user_management.tests.test_customer_auth`
2. Live: run `send_test_auth_email` and check Gmail rendering (logo, button, footer, Play Store).
