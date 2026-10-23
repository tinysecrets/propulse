# ProPulse Android SDK

Apache-2.0 Android library for registering devices, signing requests, scheduling trigger checks, and delivering local notifications.

## Requirements

- JDK 17
- Android SDK Platform 35
- Gradle Wrapper (included)

## Build and test

```bash
./gradlew lint testDebugUnitTest --no-daemon
```

Configure the API base URL and credentials through `ProPulseConfig`. Never embed a server secret key in an Android application; use a scoped public key and the request-signing flow.

## Push and alarms

The included `PropulseMessagingService` receives Firebase Cloud Messaging payloads, surfaces `title`, `body`, and optional `deeplink` fields, speaks when `speak=true`, and acknowledges a supplied `run_id`. To use remote push, configure Firebase for the consuming application and make sure the server-side provider sends FCM data messages. The SDK stores refreshed FCM tokens and includes them in device registration.

If the host app declares and is granted Android's `SCHEDULE_EXACT_ALARM` special access, `AlarmReceiver` can use exact idle-aware deadlines. Without that access, scheduled work falls back to Android's idle-aware inexact alarms; the SDK does not prompt users for special access itself.
