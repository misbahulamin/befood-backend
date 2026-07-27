# Customer Auth API

## Feature overview
This feature covers customer registration, email verification, resend verification email, login, current user, and logout for the Befood-Bachelors E-Food backend.

## Customer registration flow
1. Customer submits email, first_name, last_name, phone, occupation, is_bachelor, and password.
2. Backend validates uniqueness and format rules.
3. Backend creates an inactive Django user.
4. Backend creates a CustomerProfile.
5. Backend assigns the CUSTOMER group.
6. Backend sends an email verification link.

## Email verification flow
1. Customer clicks verification link.
2. Backend validates uid and token.
3. Backend activates the user.
4. Backend marks the profile as email verified.
5. Backend stores verification timestamp.

## Resend verification flow
If the user is unverified, the backend sends a fresh verification email. If already verified, the backend returns a helpful message.

## Login flow
Customers login with email and password only. Login is blocked until email verification is completed.

## Logout flow
Authenticated users can logout by deleting the current DRF token.

## Current user flow
Authenticated users can fetch their own user and customer profile details.

## API endpoint list
- `POST /user_management/customer/register/`
- `GET /user_management/verify-email/<uidb64>/<token>/`
- `POST /user_management/resend-verification/`
- `POST /user_management/login/`
- `GET /user_management/me/`
- `POST /user_management/logout/`

## Request examples
### Registration
```json
{
  "email": "customer@example.com",
  "first_name": "Rahim",
  "last_name": "Uddin",
  "phone": "17XXXXXXXX",
  "occupation": "student",
  "is_bachelor": true,
  "password": "StrongPassword123"
}
```

### Login
```json
{
  "email": "customer@example.com",
  "password": "StrongPassword123"
}
```

### Resend verification
```json
{
  "email": "customer@example.com"
}
```

## Response examples
### Registration success
```json
{
  "message": "Registration successful. Please check your email to verify your account.",
  "email": "customer@example.com"
}
```

### Verification success
```json
{
  "message": "Email verified successfully. You can now login."
}
```

### Login success
```json
{
  "token": "DRF_TOKEN_HERE",
  "user": {
    "id": 1,
    "email": "customer@example.com",
    "first_name": "Rahim",
    "last_name": "Uddin"
  },
  "groups": ["CUSTOMER"],
  "customer_profile": {
    "phone": "17XXXXXXXX",
    "occupation": "student",
    "is_bachelor": true,
    "is_email_verified": true
  }
}
```

## Validation rules
- Email is required and unique.
- Phone must be exactly 10 digits and contain digits only.
- Phone must be unique.
- Occupation must be one of: student, job_holder, freelancer, business_owner, unemployed, other.
- Password must pass Django password validators.
- Login only works after email verification.

## Error responses
- Invalid or expired verification link.
- Email is already verified.
- Please verify your email before login.
- Validation errors for duplicate email, duplicate phone, invalid phone, and invalid occupation.

## Email SMTP setting notes
SMTP settings are configured in the Django settings file. The password is intentionally left empty and must be added later through secure environment management.

## Frontend implementation notes for later
- Registration form must collect email, first_name, last_name, phone, occupation, is_bachelor, and password.
- Phone input must accept 10 digits only without +880.
- Occupation must be dropdown.
- is_bachelor can be yes/no or checkbox.
- After registration, show message: “Registration successful. Please check your email to verify your account.”
- Login form should use email and password.
- If login returns unverified error, show resend verification option.
