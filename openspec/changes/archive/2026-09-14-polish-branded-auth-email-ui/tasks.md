## 1. Logo and settings

- [x] 1.1 Set default `EMAIL_LOGO_URL` to public S3 URL `https://befood-media-storage.s3.ap-south-1.amazonaws.com/logo/befood_logo_for_template.png` and update `.env.example` (+ local `.env` if present with console URL)
- [x] 1.2 Add Facebook/Instagram/WhatsApp black-yellow icon assets and configurable absolute icon URLs in branding context

## 2. Template polish

- [x] 2.1 Remove all yellow brand-name highlighter spans from base + activation + password-reset HTML
- [x] 2.2 Remove “Best Regards / The Befood Team” from HTML and plain-text templates
- [x] 2.3 Replace letter social chips with black-and-yellow icon images

## 3. Verify

- [x] 3.1 Update tests/docs for logo URL, no highlighter, no Best Regards, icon imgs
- [x] 3.2 Resend sample activation (+ password_reset) to `misbahul.amin.ai@gmail.com`
