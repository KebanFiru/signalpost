"""Shared dataclasses for signalpost.

Kept in one place so detect.py, planner.py, deploy.py and instrument.py all
depend on the same, single definition of each data shape instead of
redefining or duplicating fields.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Service:
    """A single detected application service."""

    name: str
    language: str
    framework: str
    path: Path
    port_guess: int


@dataclass
class DetectionResult:
    """All facts gathered about the current environment."""

    root: Path
    has_docker: bool
    has_kubectl: bool
    existing_compose_file: Path | None
    existing_prometheus: bool
    existing_grafana: bool
    services: list[Service] = field(default_factory=list)
    cpu_count: int = 1
    total_ram_gb: float = 0.0
    disk_free_gb: float = 0.0
    arch: str = "amd64"


@dataclass
class ScrapeTarget:
    """A Prometheus scrape target derived from a detected service."""

    job_name: str
    target: str
    service: Service


@dataclass
class NotifyConfig:
    """Where fired alerts are delivered.

    ``kind`` is one of the ``NOTIFY_KIND_*`` constants. ``url`` is empty when
    ``kind`` is ``none``, which is a valid (but warned-about) configuration:
    Alertmanager still runs and groups alerts, they just stop at its UI.
    """

    kind: str
    url: str = ""

    @property
    def configured(self) -> bool:
        return bool(self.url)


@dataclass
class Plan:
    """The full set of decisions signalpost will act on."""

    log_retention_days: int
    trace_retention_days: int
    metric_retention_days: int

    sampling_pct: int

    memory_limits: dict[str, int]
    loki_ingest_mbps: int

    alert_packages: list[str]
    notify: NotifyConfig

    prometheus_port: int
    prometheus_port_conflict: bool

    install_mode: str

    scrape_targets: list[ScrapeTarget]

    decisions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class DeployResult:
    """Summary of what a deploy (real or dry-run) did or would do."""

    output_dir: Path
    dry_run: bool
    written: list[Path] = field(default_factory=list)
    backed_up: list[Path] = field(default_factory=list)
    grafana_password_file: Path | None = None
    warnings: list[str] = field(default_factory=list)
    file_hashes: dict[str, str] = field(default_factory=dict)


@dataclass
class InstrumentResult:
    """What signalpost would change (or changed) to instrument a service."""

    target_file: Path
    requirements_file: Path | None
    service_name: str
    requirements_additions: list[str]
    import_snippet: str
    instrument_call_snippet: str
    applied: bool = False
    already_instrumented: bool = False
    warnings: list[str] = field(default_factory=list)
