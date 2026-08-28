## ADDED Requirements

### Requirement: Shared branded auth email shell
Customer auth HTML emails MUST use a shared Befood-branded layout that is center-aligned and includes, in order: logo at the top, greeting, headline with yellow highlight on the brand name where shown, short body copy, a single primary CTA button (Deep Ink background, light text), recipient-email confirmation line when applicable, security disclaimer, and a brand footer. The shell MUST apply brand colors Main Yellow `#FFD100`, Deep Ink `#1C1A17`, and Warm White `#FDFCF8` for surfaces. HTML MUST be accompanied by a plain-text alternative with the same links and essential copy. The shell MUST NOT render OTP/digit verification code boxes.

#### Scenario: Activation email uses shared shell without OTP boxes
- **WHEN** the system sends a customer activation email
- **THEN** the HTML body includes the logo, greeting, primary Verify CTA, security footer content, and brand footer, and does not include a “Your verification code” digit-box section

#### Scenario: Password-reset email matches activation layout
- **WHEN** the system sends a customer password-reset email
- **THEN** the HTML uses the same shared shell structure as activation, differing only in headline, body copy, and CTA label/URL

### Requirement: Gender-aware Bangla honorific greeting
Auth email greetings MUST use the recipient display name and `CustomerProfile.gender` when available: male → `bhaiya`, female → `apu`. When gender cannot be determined, the greeting MUST be `Hello bhaiya/apu` (with optional name if present). Missing `first_name` MUST NOT cause template failure.

#### Scenario: Male customer with name
- **WHEN** an email is rendered for a customer with `first_name` set and `gender=male`
- **THEN** the greeting contains the name and `bhaiya`

#### Scenario: Gender unknown
- **WHEN** an email is rendered for a customer with null/blank gender
- **THEN** the greeting is `Hello bhaiya/apu` or `Hello {name} bhaiya/apu` without raising an error

### Requirement: Brand footer contact and store links
The shared email footer MUST include Facebook (`https://www.facebook.com/befoodbd`), Instagram (`https://instagram.com/befoodbd`), WhatsApp (`+880 1751-678409`), site (`befood.com.bd`), phone (`+880 1751-678409`), address (`K.B Aman Ali Road, Boro Mia Masjid Goli, Bakolia., Chittagong, Bangladesh, 4203`), and a Google Play badge/link to `https://play.google.com/store/apps/details?id=bd.com.befood`.

#### Scenario: Footer links present in HTML
- **WHEN** a branded auth email HTML is rendered
- **THEN** the footer contains the Play Store URL and the listed social/contact values

### Requirement: Activation email CTA is link-based verify button
Customer activation email MUST present a primary button labeled for email verification (e.g. “Verify Email Address”) whose `href` is the existing activation link. The email MUST explain that the link expires per existing token policy and MUST remind the user to ignore the message if they did not register. The email MUST NOT require the user to type a numeric verification code.

#### Scenario: Registration triggers branded activation mail
- **WHEN** a customer registers or requests resend verification
- **THEN** the system sends multipart email using the branded activation templates and the existing activation link

### Requirement: Absolute logo URL in header
The email header MUST include the Befood logo via an absolute HTTPS (or configured absolute) image URL so email clients can load it. The image MUST include meaningful `alt` text.

#### Scenario: Logo src is absolute
- **WHEN** branded auth HTML is rendered with configured logo settings
- **THEN** the top logo `img` `src` is an absolute URL and `alt` identifies Befood
