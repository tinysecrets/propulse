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
