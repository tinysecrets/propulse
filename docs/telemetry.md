# Telemetry

The repository includes Prometheus alert rules, an OpenTelemetry collector configuration, and a k6 smoke workload under `infra/`.

## Local inspection

- Review `infra/prometheus/alerts.yml` for alert conditions.
- Review `infra/otel/collector.yaml` for configured telemetry receivers and exporters.
- Review `infra/k6/smoke.js` before running load tests against any target.

Telemetry collection and alert delivery depend on the runtime configuration and endpoints supplied by the operator. Do not send production traffic to a local or staging stack without explicit authorization and capacity checks.
