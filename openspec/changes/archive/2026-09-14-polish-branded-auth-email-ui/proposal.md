## Why

Live QA of branded auth emails showed broken logo (AWS Console URL is not a public image URL), yellow highlighter on every “Befood” mention looking noisy, letter-only social chips instead of brand icons, and an unnecessary “Best Regards / The Befood Team” block.

## What Changes

- Point `EMAIL_LOGO_URL` at the public S3 object URL for `logo/befood_logo_for_template.png` (not the AWS Console link).
- Remove all yellow text-highlight backgrounds from “Befood” / brand name spans in auth email HTML.
- Remove the “Best Regards, The Befood Team” sign-off block from HTML and plain-text auth emails.
- Replace Facebook / Instagram / WhatsApp letter chips with black-and-yellow icon images (absolute HTTPS URLs usable by email clients).

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `branded-auth-emails`: Logo URL contract, no yellow brand-name highlighters, no Best Regards sign-off, black/yellow social icon images in footer.

## Impact

- `templates/emails/base_branded_email.html` and activation/password-reset HTML/TXT templates
- `core/settings/base.py`, `.env.example`, local `EMAIL_LOGO_URL`
- `email_branding.py` context (icon URLs)
- Optional static/S3 icon assets under `logo/` or `static/emails/`
- Tests/docs asserting logo URL and footer shape
