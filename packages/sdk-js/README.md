# @wah-lah/propulse

Apache-2.0 JavaScript/TypeScript client for the ProPulse API.

## Requirements

Node.js 18 or newer.

## Install and build

```bash
npm ci
npm run lint
npm test
npm run build
```

Use a scoped public client key in browser/mobile applications. Do not ship secret server keys in client bundles. The client signs requests with the configured public-key signing secret supplied by your secure provisioning flow.
