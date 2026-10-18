# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-04

First public release. Renamed from `obskit` before publication.

### Added

- `signalpost init` — detect the host environment and print the full plan with
  a plain-language rationale for every decision.
- `signalpost plan` — the decisions and resulting settings without writing
  anything to disk.
- `signalpost deploy` — render the stack into `./observability/`, with
  `--dry-run` and `--output`. Existing files are backed up to `<name>.bak`. A
  24-character Grafana admin password is generated once into
  `secrets/grafana_admin_password.txt` (mode 644 in docker mode, tightened to
  600 in binary mode — see SECURITY.md) and reused across deploys.
- `signalpost alerts` — list the alert packages the current plan enables and
  what each one covers.
- `signalpost dashboards` — list the provisioned Grafana dashboards, or render
  one in the terminal as ASCII with `--preview`, animated with `--live`.
- `signalpost instrument <path>` — show the OpenTelemetry wiring a detected
  FastAPI service needs; `--apply` writes it, and is a no-op on a second run.
- `--notify` on `init`/`plan`/`deploy` — route fired alerts to a Slack,
  Discord, or generic HTTPS webhook. Alertmanager is deployed either way, with
  a loud warning when no receiver is configured.

### Install modes

- **docker** — `docker-compose.signalpost.yml` plus `configs/`,
  `provisioning/`, `alerts/` and `secrets/`. Chosen when Docker is present and
  the host has at least 2 CPUs and 4GB RAM.
- **binary** — the same configuration plus an `install.sh` that fetches
  Prometheus, Loki, Tempo, Grafana, otel-collector-contrib and node_exporter
  from their official releases and installs each as a `signalpost-*.service`
  systemd unit. Chosen automatically on constrained or Docker-less hosts.

### Alert packages

- `host-basics` — CPU, memory, disk and node_exporter availability, plus
  I/O-wait and kernel-PSI memory-pressure alerts.
- `stack-selfhealth` — component uptime, Loki ingest errors, collector queue
  health.
- `http-red` — rate, errors and duration, scoped to detected web services.
- `slo-burn-rate` — Google SRE Workbook-style multi-window, multi-burn-rate
  alerting against a 99.9% target (fast-burn 5m/1h, slow-burn 30m/6h).

### Dashboards

Provisioned into a `signalpost` folder in Grafana: **Host Basics**, **Stack
Self-Health**, and **HTTP RED** (which pairs RED metrics with a live Logs
panel scoped to the detected services).

Datasources ship with pinned UIDs so trace ↔ log ↔ metric correlation works on
first boot rather than after manual configuration.

[Unreleased]: https://github.com/KebanFiru/signalpost/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/KebanFiru/signalpost/releases/tag/v0.1.0
