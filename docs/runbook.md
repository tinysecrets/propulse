# Operations runbook

## Local lifecycle

```bash
make doctor
make up
make logs
make demo
make test
make down
```

Use `make down` to stop the local stack. Avoid destructive targets such as `make nuke` unless removing local data is intended.

## Health and troubleshooting

- Check `make doctor` first for environment and dependency checks.
- Use `make logs` to inspect service logs.
- Confirm the configured MongoDB and Redis URLs in the local environment.
- Confirm adapter settings; the local default adapters are intended for development and demonstration.
- If a service does not become healthy, inspect its own logs before restarting the whole stack.

## Production incident response

Do not use the local demo checklist as a production incident procedure. Production deployment, backups, key rotation, alert routing, rollback, and access controls must be configured and tested for the selected hosting environment before launch.
