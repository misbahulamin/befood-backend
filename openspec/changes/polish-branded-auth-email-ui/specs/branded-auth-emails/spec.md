## MODIFIED Requirements

### Requirement: Shared branded auth email shell
Customer auth HTML emails MUST use a shared Befood-branded layout that is center-aligned and includes, in order: logo at the top, greeting, headline, short body copy, a single primary CTA button (Deep Ink background, light text), recipient-email confirmation line when applicable, security disclaimer, and a brand footer. The shell MUST apply brand colors Main Yellow `#FFD100`, Deep Ink `#1C1A17`, and Warm White `#FDFCF8` for surfaces. Brand name text MUST NOT use yellow highlighter/background spans. The shell MUST NOT include a “Best Regards / The Befood Team” sign-off block. HTML MUST be accompanied by a plain-text alternative with the same links and essential copy. The shell MUST NOT render OTP/digit verification code boxes.

#### Scenario: Activation email uses shared shell without OTP boxes
- **WHEN** the system sends a customer activation email
- **THEN** the HTML body includes the logo, greeting, primary Verify CTA, security footer content, and brand footer, and does not include a “Your verification code” digit-box section

#### Scenario: No yellow brand-name highlighter
- **WHEN** branded auth HTML is rendered
- **THEN** the body and footer do not wrap the brand name in yellow background highlight spans

#### Scenario: No Best Regards sign-off
- **WHEN** branded auth HTML or plain-text is rendered
- **THEN** the content does not include “Best Regards” or “The Befood Team” sign-off lines

### Requirement: Absolute logo URL in header
The email header MUST include the Befood logo via an absolute public HTTPS image URL (S3 object URL or equivalent CDN), not an AWS Console page URL. The image MUST include meaningful `alt` text.

#### Scenario: Logo src is absolute public object URL
- **WHEN** branded auth HTML is rendered with default logo settings
- **THEN** the top logo `img` `src` is a public object URL under the media bucket (e.g. `.../logo/befood_logo_for_template.png`) and loads without console authentication

### Requirement: Brand footer contact and store links
The shared email footer MUST include Facebook (`https://www.facebook.com/befoodbd`), Instagram (`https://instagram.com/befoodbd`), WhatsApp (`+880 1751-678409`), site (`befood.com.bd`), phone (`+880 1751-678409`), address (`K.B Aman Ali Road, Boro Mia Masjid Goli, Bakolia., Chittagong, Bangladesh, 4203`), and a Google Play badge/link to `https://play.google.com/store/apps/details?id=bd.com.befood`. Social entries MUST use black-and-yellow icon images (not letter-only chips).

#### Scenario: Footer links present in HTML
- **WHEN** a branded auth email HTML is rendered
- **THEN** the footer contains the Play Store URL and the listed social/contact values

#### Scenario: Social icons are images
- **WHEN** a branded auth email HTML is rendered
- **THEN** Facebook, Instagram, and WhatsApp footer controls use `<img>` icons with absolute HTTPS sources
