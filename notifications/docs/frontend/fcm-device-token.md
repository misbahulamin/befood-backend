# FCM Device Token — Flutter Integration Guide

## What this is

Your Flutter app must tell the Befood backend which FCM device token belongs to the logged-in user. The backend stores tokens so it can later send push notifications to:

- one user (all their devices)
- one specific device token
- all active devices (broadcast)

This guide covers **register**, **refresh**, and **remove** — you do **not** need Firebase credentials on the backend side for these calls.

## Base URL and headers

| Item | Value |
|------|-------|
| Base path | `/notifications/` |
| Auth | `Authorization: Token <token_from_login>` |
| Content-Type | `application/json` |
| Optional | `X-Client-Type: mobile` |

Obtain the DRF auth token from the existing login endpoint (`POST /user_management/login/` or your app's login flow).

## Workflow (step by step)

### 1. After successful login

1. User logs in → you receive `token` (DRF auth key).
2. Request FCM token from Firebase in Flutter (`FirebaseMessaging.instance.getToken()`).
3. Call **register** (below) with the FCM token and platform.

### 2. When FCM token refreshes

Firebase may emit a new token while the app runs. Listen for token refresh and call **register** again with the new token. The backend upserts — no duplicate rows.

### 3. On logout

Before clearing local auth state, call **remove** with the current FCM token so the backend stops targeting this device for the old user.

If the user logs in as someone else on the same phone without calling remove, the backend will reassign the token to the new user on the next register (expected behavior).

---

## POST `/notifications/device-token/`

**Why:** Create or refresh the device record for push delivery.

**When:** After login, on app start (if logged in), and on FCM token refresh.

**Request**

```json
{
  "token": "fcm_token_string_from_firebase",
  "platform": "android",
  "device_name": "Pixel 8",
  "app_version": "1.2.0"
}
```

| Field | Required | Meaning |
|-------|----------|---------|
| `token` | Yes | FCM device token (min 10 chars) |
| `platform` | Yes | `android`, `ios`, or `web` |
| `device_name` | No | Human-readable device label |
| `app_version` | No | Your app version string |

**Success — 200**

```json
{
  "success": true,
  "message": "Device registered successfully"
}
```

**Errors**

| Status | Meaning |
|--------|---------|
| `401` | Not logged in — send auth header |
| `400` | Invalid body (bad platform, empty token, field too long) |

**Example (Dart / http)**

```dart
final response = await http.post(
  Uri.parse('$baseUrl/notifications/device-token/'),
  headers: {
    'Authorization': 'Token $authToken',
    'Content-Type': 'application/json',
    'X-Client-Type': 'mobile',
  },
  body: jsonEncode({
    'token': fcmToken,
    'platform': Platform.isAndroid ? 'android' : 'ios',
    'device_name': deviceName,
    'app_version': packageInfo.version,
  }),
);
```

---

## POST `/notifications/device-token/remove/`

**Why:** Stop push to this device for the current user without deleting audit history.

**When:** User taps Logout.

**Request**

```json
{
  "token": "fcm_token_string_from_firebase"
}
```

**Success — 200**

```json
{
  "success": true,
  "message": "Device deactivated successfully"
}
```

**Errors**

| Status | Meaning |
|--------|---------|
| `401` | Not logged in |
| `404` | Token not found or not owned by this user |
| `400` | Invalid token field |

Call this **before** deleting the local auth token so the request is still authenticated.

---

## Recommended Flutter checklist

- [ ] Register after login when FCM token is available
- [ ] Re-register on `onTokenRefresh`
- [ ] Remove on logout (authenticated)
- [ ] Handle `401` by redirecting to login
- [ ] Do not send another user's ID — backend uses auth token only

## Swagger

Interactive docs: `/api/docs/` → **Notifications** tag.
