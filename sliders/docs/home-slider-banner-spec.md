# Home slider banner spec (admin upload guide)

Recommended asset for BeFood mobile home carousel (`KSize.heroBannerHeight` = 168, full width, `BoxFit.cover`).

- **Canvas:** 1200 × 560 px (≈ 15:7). Alternative 1080 × 540 (2:1) is acceptable if cropped carefully.
- **Formats:** JPEG / JPG / PNG / WebP.
- **File size:** under **500 KB** preferred; hard API limit is **5 MB**.
- **Safe area:** keep logo/text away from the outer 8% (carousel uses `viewportFraction: 0.92`).
- **Content:** no required CTA in v1 (images are not tappable).
- **Inactive rows:** set `is_active=false` instead of deleting when pausing a campaign.

Public feed: `GET /sliders/` (active only, priority ASC). Admin: `GET/POST/PATCH/DELETE /sliders/admin/`.
