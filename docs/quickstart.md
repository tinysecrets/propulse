# Quickstart

## Requirements

- Docker Engine with the Compose plugin
- Git
- Python 3.12 and `uv` for local development
- Node.js 18+ for the JavaScript SDK

## Start the local stack

```bash
cp .env.example .env
make up
make doctor
make demo
```

The `.env.example` file documents supported defaults. Keep real credentials in a local, untracked `.env` file or a secret manager; never commit them.

## Optional Android push delivery

The local stack remains cloud-free by default. The voice worker sends Android data messages through Firebase Cloud Messaging HTTP v1 only when `FCM_ENABLED=true` and a service account is configured. The worker uses the service-account credential to obtain short-lived OAuth access tokens; it never logs the credential or device token.

1. Add Firebase to the consuming Android application, include its `google-services.json`, apply the Google Services Gradle plugin, and verify that FCM registration yields a device token. See the [official Firebase Android setup](https://firebase.google.com/docs/android/setup) and [FCM receive-message guide](https://firebase.google.com/docs/cloud-messaging/android/receive-messages).
2. In the Firebase/Google Cloud project, enable Firebase Cloud Messaging API and create a service account with the minimum role required to send FCM messages. Keep its JSON private. Do not place it in Git, an Android app, an image, or a log.
3. Configure the voice-worker environment only: `FCM_ENABLED=true`, `FCM_PROJECT_ID`, and `FCM_SERVICE_ACCOUNT_JSON`. For local Compose, put the compact single-line JSON in the untracked `.env` file or use a secrets manager/Compose override to inject it only into the `voice` service. Do not set this secret on the API, scheduler, or agent containers.
4. Rebuild/restart the voice worker after the secret is configured. Register the Android device again so the FCM token is saved; send a test pulse and verify delivery/acknowledgement in the worker logs and notification record.

Without the Firebase app configuration and project credentials, FCM delivery deliberately remains disabled. Android local notifications and on-device speech still compile and are covered by the Android SDK test suite.

## Verify

```bash
make test
make lint
cd packages/sdk-js
npm ci
npm test
npm run build
npm run lint
```

The local demonstration validates the configured local path; it does not establish production readiness, external billing setup, DNS, or deployment credentials.
