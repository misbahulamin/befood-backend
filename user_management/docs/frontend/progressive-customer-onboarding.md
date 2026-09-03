# Progressive Customer Onboarding (Frontend)

## Summary

Customer signup is now **email + password**. After email verification and login, the app collects remaining profile fields in small steps. Each step should call `PATCH /user_management/customer/profile/` and persist immediately — do not hold multi-step data only in client memory waiting for a final submit.

**Auth:** `Authorization: Token <token>`  
**Base:** `/user_management/`  
**Clients:** mobile + web customer apps

---

## Three different “complete” states

| Concept | Meaning | How to know |
| --- | --- | --- |
| Account registration complete | Email verified; user can log in | `customer_profile.is_email_verified === true` |
| Onboarding profile complete | Name, phone, occupation, bachelor flag, gender filled | `onboarding_completion.completed === true` |
| Extended profile complete | Food/delivery/emergency fields score ≥ 80% | `profile_completed` / `profile_completion_percentage` |

Do **not** treat incomplete onboarding as a login blocker.

---

## Suggested client flow

1. `POST /user_management/customer/register/` with `{ email, password }` (pending only — no User yet)
2. User verifies email via OTP or link → **account is created**
3. `POST /user_management/login/`
4. `GET /user_management/me/` → read `onboarding_completion.missing_fields`
5. For each UI step, `PATCH /user_management/customer/profile/` with only that step’s fields
6. Optionally refresh `/me` or use PATCH response `onboarding_completion`

Modal timing / when to ask is **frontend-only**.

---

## Onboarding completion payload

```json
{
  "onboarding_completion": {
    "completed": false,
    "missing_fields": ["phone", "gender"],
    "completion_percentage": 67
  }
}
```

Tracked fields: `first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`, `gender`.

- Names missing when blank/whitespace
- `phone` / `occupation` / `gender` missing when null/blank
- `is_bachelor` missing only when `null` (`true` and `false` both count as present)

---

## Progressive PATCH examples

### Names
```json
{ "first_name": "John", "last_name": "Doe" }
```

### Phone
```json
{ "phone": "1712345678" }
```

### Demographics
```json
{
  "gender": "male",
  "is_bachelor": true,
  "occupation": "student"
}
```

### Gender choices
`male` | `female` | `other` | `prefer_not_to_say`

### Occupation choices
`student` | `job_holder` | `freelancer` | `business_owner` | `unemployed` | `other`

### Marital / bachelor
There is **no** `marital_status` field. Use boolean `is_bachelor`.

---

## Writable vs privileged

**Writable via PATCH (among others):**  
`first_name`, `last_name`, `phone`, `occupation`, `is_bachelor`, `gender`, plus existing extended fields (`birth_date`, preferences, etc.)

**Not writable (ignored / server-owned):**  
`is_email_verified`, `email_verified_at`, `profile_completed`, `profile_completion_percentage`, roles, `is_active`

---

## Errors

Use existing DRF field errors, e.g.:

```json
{ "phone": ["Phone must be exactly 10 digits and digits only."] }
```

Invalid one field must not clear other already-saved profile values.

---

## Legacy registration clients

During the compatibility window, register may still accept the old seven-field body. Prefer minimal register + progressive PATCH for new builds.
