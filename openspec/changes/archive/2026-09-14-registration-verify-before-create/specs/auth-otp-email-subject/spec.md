## ADDED Requirements

### Requirement: OTP appears first in auth email subjects
The system SHALL place the plaintext OTP/code at the beginning of the email subject for customer emails that deliver an auth OTP. The subject MUST make the code readable in inbox previews without opening the message. Email HTML and plain-text body templates MUST NOT change layout or styling as part of this requirement.

#### Scenario: Email verification subject starts with OTP
- **WHEN** the system sends a customer activation/verification email that includes a newly issued OTP
- **THEN** the email subject starts with the six-digit OTP followed by wording equivalent to “is your sign-in verification code” (for example `723948 is your sign-in verification code`)

#### Scenario: Password reset subject starts with OTP
- **WHEN** the system sends a customer password-reset email that includes a newly issued OTP
- **THEN** the email subject starts with the six-digit OTP followed by purpose-appropriate wording that still presents the code first (for example `723948 is your password reset code`)

#### Scenario: Body templates remain unchanged
- **WHEN** activation or password-reset emails are rendered after this change
- **THEN** the existing HTML and text body template structure and styling remain the same aside from already-supported context variables such as `otp_code`

### Requirement: Subject update covers all OTP-bearing auth emails
The system SHALL apply the code-first subject rule to registration/email verification OTP sends and to forgot/reset password OTP sends. The system MUST NOT require separate “forgot” vs “reset” subject families beyond the existing shared password-reset email templates.

#### Scenario: Register and resend use the verification subject format
- **WHEN** registration or resend verification issues and sends an OTP email
- **THEN** the subject uses the verification code-first format

#### Scenario: Password reset request uses the reset subject format
- **WHEN** password reset is requested and an OTP email is sent
- **THEN** the subject uses the password-reset code-first format and password-reset confirm/validate behavior is otherwise unchanged
