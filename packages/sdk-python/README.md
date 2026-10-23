# ProPulse Python SDK

Apache-2.0 Python client for the ProPulse API.

## Install

```bash
pip install propulse-sdk
```

## Use

```python
from propulse_sdk import ProPulse

with ProPulse(key="pp_pub_...", secret="...") as client:
    result = client.signal("cart_idle", install_id="install-1")
    print(result["pulse_run_id"])
```

Do not ship secret server keys in public clients. Keep secrets server-side, use scoped public keys, and rotate exposed credentials.
