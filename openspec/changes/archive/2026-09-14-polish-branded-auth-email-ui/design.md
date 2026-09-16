## Context

Branded auth emails shipped in `professional-auth-email-templates`. Inbox QA found: console S3 link used as logo `src` (broken image), yellow highlighter spans on brand words, text “f/ig/wa” social chips, and “Best Regards / The Befood Team” that product wants removed.

Public logo object works at:
`https://befood-media-storage.s3.ap-south-1.amazonaws.com/logo/befood_logo_for_template.png`

## Goals / Non-Goals

**Goals:**
- Fix logo rendering via public HTTPS object URL.
- Strip yellow highlighter styling from brand name text.
- Remove Best Regards sign-off.
- Use Facebook, Instagram, WhatsApp icons in Deep Ink + yellow.

**Non-Goals:**
- Redesigning overall email layout or CTA.
- Changing activation/reset token APIs.

## Decisions

1. **Logo default** → S3 public object URL above (override via `EMAIL_LOGO_URL`).
2. **No highlighter** → plain bold/text for brand name; yellow reserved for icons/accents only if needed on icon discs.
3. **Social icons** → PNG assets (yellow circle + black glyph), hosted on same S3 `logo/` prefix (or configurable `EMAIL_*_ICON_URL`), referenced as `<img>` in footer.
4. **Sign-off** → remove entirely; footer branding remains.

## Risks / Trade-offs

- [S3 object not public] → Verified 200 on logo URL; icons uploaded with public-read or same ACL as logo.
- [Email clients block remote images] → `alt` text on icons; text links remain in footer.

## Open Questions

- None for this polish.
