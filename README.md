# signalpost

[![CI](https://github.com/KebanFiru/signalpost/actions/workflows/ci.yml/badge.svg)](https://github.com/KebanFiru/signalpost/actions/workflows/ci.yml)

**Your 8-person team needs observability. It does not need a week of reading
four projects' docs to pick retention windows.**

signalpost stands up a Grafana + Loki + Tempo + Prometheus + OpenTelemetry
Collector stack on one host — and, more importantly, makes the dozen
configuration decisions that come with it, then shows you *why* it made each
one.

```bash
git clone https://github.com/KebanFiru/signalpost.git
cd signalpost
pip install .
signalpost plan
```

## What it actually does

Plenty of tools can already *install* these components. What they can't do
is tell a team with no observability experience what retention window fits
their disk, whether to sample traces, how much RAM to give Loki before it
starves the app it's monitoring, or which alerts are worth paging on.

signalpost decides all of that from your actual machine, and prints its
reasoning:

```console
$ signalpost plan
                                        Decisions
┏━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ #   ┃ Rationale                                                                        ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1   │ Disk free 8GB < 40GB -> conservative retention: logs 3d / traces 1d / metrics    │
│     │ 7d.                                                                              │
│ 2   │ 0 service(s) detected (<= 5) -> 100% trace sampling. At low traffic, sampling    │
│     │ only risks losing the one trace you're looking for.                              │
│ 3   │ Host RAM 15GB >= 8GB -> mid memory tier for all components.                      │
│ 4   │ Loki per-stream ingest limit set to 8MB/s (RAM >= 8GB) to protect the stack from │
│     │ a single service's log flood.                                                    │
│ 5   │ host-basics and stack-selfhealth alert packages are always enabled.              │
│ 6   │ No --notify target given -> Alertmanager is still deployed (so alerts have       │
│     │ somewhere to land and can be silenced/grouped), but with no receiver configured. │
│ 7   │ No existing Prometheus detected -> using default port 9090.                      │
│ 8   │ Docker available and host has 16 CPU(s) / 15GB RAM -> using docker-compose       │
│     │ (simplest to operate and upgrade).                                               │
│ 9   │ No services detected -> no application scrape targets added (host-basics only).  │
└─────┴──────────────────────────────────────────────────────────────────────────────────┘
╭─────────────────────────────────────── Warning ────────────────────────────────────────╮
│ Only 8GB free disk detected. Retention was cut to the minimum tier; monitor disk usage │
│ closely and consider adding storage.                                                   │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

Nothing is written to disk until you run `signalpost deploy` — you get the
full plan and its reasoning up front, before anything changes.

## Quickstart

```bash
git clone https://github.com/KebanFiru/signalpost.git
cd signalpost
pip install .

cd ~/my-project
signalpost plan                        
signalpost deploy                      
cd observability
docker compose -f docker-compose.signalpost.yml up -d
```

Grafana is on `:3000`. The admin password was generated for you into
`observability/secrets/grafana_admin_password.txt` (mode 644 — world-readable
so containers running as an unprivileged, fixed-UID user can read a
bind-mounted file, see [SECURITY.md](SECURITY.md)) and is reused across
deploys.

To actually get alerted, pass a webhook:

```bash
signalpost deploy --notify https://hooks.slack.com/services/...
```

## The decisions it makes for you

This table is the product. Every row is a call your team would otherwise
make badly, or not at all.

| Heuristic | Rule | Why |
|---|---|---|
| **Retention** | ≥100GB free disk → 14d logs / 7d traces / 30d metrics; ≥40GB → 7d/3d/15d; below → 3d/1d/7d (+ warning) | Retention is a disk-budget problem before it's a "how long do I need this" problem. |
| **Trace sampling** | ≤5 services → 100%; >5 → 25% head sampling | At low traffic, sampling only risks losing the one trace you were looking for. |
| **Memory limits** | Three RAM tiers (≥16GB / ≥8GB / below), per-component | Prevents the stack from starving the host it's supposed to be observing. |
| **Loki ingest limit** | 8MB/s per stream (RAM ≥8GB), else 4MB/s | Caps one misbehaving service's log flood from taking down ingestion for everyone. |
| **Alert packages** | `host-basics` + `stack-selfhealth` always; `http-red` (+ `slo-burn-rate`) if a Python web service is detected | RED alerts are only meaningful — and only scoped — to services signalpost actually found. |
| **Alert delivery** | Alertmanager always deployed; receiver configured only if `--notify` is given, warns loudly if not | Alerts that fire into a void are worse than no alerts, because they feel like coverage. |
| **Prometheus port** | 9090 by default; 9091 if an existing Prometheus container is running | Avoids a silent port collision with whatever you already have running. |
| **Install mode** | **docker** if Docker is present and host has ≥2 CPUs / ≥4GB RAM; otherwise **binary** (systemd units from official releases) | On a constrained VPS the Docker daemon's own overhead competes with the stack meant to monitor it. |
| **Scrape targets** | Derived from each detected service's guessed port | No manual `prometheus.yml` editing for the common case, in either mode. |

`slo-burn-rate` implements Google SRE Workbook-style multi-window,
multi-burn-rate alerting (99.9% target; fast-burn 5m/1h, slow-burn 30m/6h) —
the shape large tech companies use to page on real error-budget risk instead
of noisy static thresholds. `host-basics` includes I/O-wait and kernel-PSI
memory-pressure alerts for the same reason.

## Correlation that works on first boot

Three datasources come pre-wired with **pinned UIDs**, which is what makes
cross-links survive provisioning:

- Click a `trace_id` in a Loki log line → jump to that trace in Tempo.
- Click a span in Tempo → jump to its logs in Loki, or its service graph in
  Prometheus.
- Click an exemplar on a Prometheus graph → jump to the trace that produced
  that data point.

Three dashboards are provisioned into a `signalpost` folder: **Host Basics**,
**Stack Self-Health**, and **HTTP RED** (with a live Logs panel scoped to
your detected services, sitting right next to the RED metrics).

You can look at them before you install anything:

```console
$ signalpost dashboards --preview host-basics
╭─────────────────────────────── signalpost / Host Basics ───────────────────────────────╮
│ CPU            ##########--------------------  35.0%                                   │
│ Memory         ###############---------------  50.0%                                   │
│ Disk           ############------------------  40.0%                                   │
│ I/O wait       #-----------------------------   5.0%                                   │
│ CPU trend      =                                                                       │
│ Mem trend      +                                                                       │
╰────────────────────────────────────────────────────────────────────────────────────────╯
```

Add `--live` to animate it against simulated data.

## Why not just…

**…install the components yourself?** Plenty of tooling can stand up each
piece. What it hands you is a blank `loki-config.yaml` you still don't know
how to fill in — signalpost is the opinions, not the plumbing, and it targets
one host, not a cluster you may not have.

**…use a hosted/managed observability platform?** If the bill and shipping
your logs off-box both work for you, that's a reasonable call — genuinely.
signalpost is for teams that need to self-host: cost, data residency,
air-gapped networks, or an existing host that's already paid for.

**…do it yourself, from scratch?** You can, and it takes about a week the
first time. That week is the product.

## Commands

| Command | What it does |
|---|---|
| `signalpost init` | Detect the environment, show the full plan with rationale. Start here. |
| `signalpost plan` | Just the plan, writes nothing. Re-run after your hardware or services change. |
| `signalpost deploy` | Render into `./observability/`. `--dry-run` to preview, `--output` for a custom path. Existing files whose content would change are backed up to `<name>.bak.<UTC timestamp>`. |
| `signalpost alerts` | Which alert packages the current plan enables, and what each covers. |
| `signalpost dashboards` | List provisioned dashboards, or `--preview <name>` one as ASCII (`--live` to animate). |
| `signalpost instrument <path>` | Show the OTel wiring a detected FastAPI service needs. `--apply` to write it. |

Global flags: `--path` (directory to scan), `--notify` (Slack/Discord/HTTPS
webhook for alerts).

`instrument --apply` only edits files it's confident about (it looks for an
`app = FastAPI(...)` assignment) and otherwise leaves them untouched. It
marks what it instrumented, so a second run is a no-op.

### Two install modes

- **docker** — `docker-compose.signalpost.yml` + `configs/`, `provisioning/`,
  `alerts/`, `secrets/`.
- **binary** — the same configs plus an `install.sh` that pulls Prometheus,
  Loki, Tempo, Grafana, otel-collector-contrib and node_exporter from their
  official releases and installs each as a `signalpost-*.service` systemd
  unit. Chosen automatically on constrained or Docker-less hosts. Review the
  script, then `sudo ./install.sh`.

## How it's built

```
detect.py  ──facts──▶  planner.py  ──justified decisions──▶  Plan
(no opinions)          (all the opinions)                     │
                                                              ▼
                                                          deploy.py
                                                    renders templates/
                                                     → ./observability
```

`detect.py` never makes a judgment call — it reports facts only (disk, RAM,
CPU, detected services, running containers). `planner.py` holds every
heuristic, and each decision carries the plain-language reason that `plan`
prints. `constants.py` holds every magic number in one place, so tuning the
opinions never means grepping through logic.

## Development

```bash
pip install -e ".[dev]"
pytest
```

`make test` / `make lint` run the same inside Docker. `make smoke-docker`
renders a real stack, brings it up with docker compose, and waits for every
component to report healthy.

## Roadmap

signalpost targets one host today. These are the items planned next:

- [ ] **Reverse proxy + TLS** — generate an nginx/Caddy config in front of
  Grafana and the OTLP receivers instead of leaving them on plain HTTP.
- [ ] **Multi-host over a private network** — for hosts joined by a virtual
  LAN (Tailscale, WireGuard, etc.), point each host's OTel Collector and
  Prometheus remote_write at one shared Grafana/Loki/Tempo instance instead
  of running a fully separate stack per host. Not supported yet; today each
  host gets its own independent stack.

## License

MIT — see [LICENSE](LICENSE).
