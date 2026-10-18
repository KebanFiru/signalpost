"""The expert system: turns detected facts into concrete, justified decisions.

Every decision this module makes is recorded as a human-readable string in
``Plan.decisions`` so the CLI can show the user *why*, not just *what*. All
thresholds and tier tables it applies live in :mod:`signalpost.constants`.
"""

from __future__ import annotations

from signalpost.constants import (
    ALERTMANAGER_PORT,
    BINARY_MODE_CPU_THRESHOLD,
    BINARY_MODE_RAM_GB_THRESHOLD,
    DISK_TIER_LARGE_GB,
    DISK_TIER_MEDIUM_GB,
    INSTALL_MODE_BINARY,
    INSTALL_MODE_DOCKER,
    LOKI_INGEST_MBPS_LOW,
    LOKI_INGEST_MBPS_NORMAL,
    MEMORY_LIMITS_HIGH,
    MEMORY_LIMITS_LOW,
    MEMORY_LIMITS_MID,
    NOTIFY_KIND_LABELS,
    NOTIFY_KIND_NONE,
    NOTIFY_URL_PATTERNS,
    PROMETHEUS_CONFLICT_PORT,
    PROMETHEUS_DEFAULT_PORT,
    RAM_TIER_HIGH_GB,
    RAM_TIER_MID_GB,
    RETENTION_LARGE,
    RETENTION_MEDIUM,
    RETENTION_SMALL,
    SAMPLING_FULL_PCT,
    SAMPLING_HEAD_PCT,
    SAMPLING_SERVICE_THRESHOLD,
)
from signalpost.detect import DetectionResult
from signalpost.models import NotifyConfig, Plan, ScrapeTarget, Service


def _plan_retention(disk_free_gb: float, decisions: list[str], warnings: list[str]) -> dict[str, int]:
    if disk_free_gb >= DISK_TIER_LARGE_GB:
        tier = RETENTION_LARGE
        decisions.append(
            f"Disk free {disk_free_gb:.0f}GB >= {DISK_TIER_LARGE_GB}GB -> generous retention: "
            f"logs {tier['log_days']}d / traces {tier['trace_days']}d / metrics {tier['metric_days']}d."
        )
    elif disk_free_gb >= DISK_TIER_MEDIUM_GB:
        tier = RETENTION_MEDIUM
        decisions.append(
            f"Disk free {disk_free_gb:.0f}GB >= {DISK_TIER_MEDIUM_GB}GB -> moderate retention: "
            f"logs {tier['log_days']}d / traces {tier['trace_days']}d / metrics {tier['metric_days']}d."
        )
    else:
        tier = RETENTION_SMALL
        decisions.append(
            f"Disk free {disk_free_gb:.0f}GB < {DISK_TIER_MEDIUM_GB}GB -> conservative retention: "
            f"logs {tier['log_days']}d / traces {tier['trace_days']}d / metrics {tier['metric_days']}d."
        )
        warnings.append(
            f"Only {disk_free_gb:.0f}GB free disk detected. Retention was cut to the minimum tier; "
            "monitor disk usage closely and consider adding storage."
        )
    return dict(tier)


def _plan_sampling(service_count: int, decisions: list[str]) -> int:
    if service_count <= SAMPLING_SERVICE_THRESHOLD:
        decisions.append(
            f"{service_count} service(s) detected (<= {SAMPLING_SERVICE_THRESHOLD}) -> 100% trace sampling. "
            "At low traffic, sampling only risks losing the one trace you're looking for."
        )
        return SAMPLING_FULL_PCT
    decisions.append(
        f"{service_count} services detected (> {SAMPLING_SERVICE_THRESHOLD}) -> "
        f"{SAMPLING_HEAD_PCT}% head sampling to bound collector/storage load."
    )
    return SAMPLING_HEAD_PCT


def _plan_memory(total_ram_gb: float, decisions: list[str]) -> dict[str, int]:
    if total_ram_gb >= RAM_TIER_HIGH_GB:
        limits = MEMORY_LIMITS_HIGH
        decisions.append(
            f"Host RAM {total_ram_gb:.0f}GB >= {RAM_TIER_HIGH_GB}GB -> high memory tier for all components."
        )
    elif total_ram_gb >= RAM_TIER_MID_GB:
        limits = MEMORY_LIMITS_MID
        decisions.append(
            f"Host RAM {total_ram_gb:.0f}GB >= {RAM_TIER_MID_GB}GB -> mid memory tier for all components."
        )
    else:
        limits = MEMORY_LIMITS_LOW
        decisions.append(
            f"Host RAM {total_ram_gb:.0f}GB < {RAM_TIER_MID_GB}GB -> low memory tier to avoid starving "
            "the host; expect tighter buffers and more frequent flushing."
        )
    return dict(limits)


def _plan_loki_ingest(total_ram_gb: float, decisions: list[str]) -> int:
    if total_ram_gb >= RAM_TIER_MID_GB:
        rate = LOKI_INGEST_MBPS_NORMAL
    else:
        rate = LOKI_INGEST_MBPS_LOW
    decisions.append(
        f"Loki per-stream ingest limit set to {rate}MB/s (RAM {'>= ' if rate == LOKI_INGEST_MBPS_NORMAL else '< '}"
        f"{RAM_TIER_MID_GB}GB) to protect the stack from a single service's log flood."
    )
    return rate


def _plan_alerts(services: list[Service], decisions: list[str]) -> list[str]:
    packages = ["host-basics", "stack-selfhealth"]
    decisions.append("host-basics and stack-selfhealth alert packages are always enabled.")
    has_python_web = any(
        s.language == "python" and s.framework in ("fastapi", "flask", "django") for s in services
    )
    if has_python_web:
        packages.append("http-red")
        decisions.append(
            "Python web service(s) detected -> enabling http-red alert package (Rate/Errors/Duration)."
        )
        packages.append("slo-burn-rate")
        decisions.append(
            "http-red is enabled -> also enabling slo-burn-rate (Google SRE-style multi-window "
            "multi-burn-rate SLO alerts) since it reuses the same RED metrics."
        )
    return packages


def _plan_notifications(
    notify_url: str | None, decisions: list[str], warnings: list[str]
) -> NotifyConfig:
    """Decide where fired alerts are delivered.

    Alert *rules* without a delivery path are the most common way a
    self-hosted stack quietly fails: everything looks configured, and nobody
    is ever paged. signalpost therefore always renders Alertmanager, and treats a
    missing notify target as a warning rather than a silent default.
    """
    if not notify_url:
        warnings.append(
            "No notification target configured. Alerts will fire and group in Alertmanager "
            f"(:{ALERTMANAGER_PORT}) but will not reach anyone. Re-run with "
            "--notify <slack-or-discord-webhook-url> to route them."
        )
        decisions.append(
            "No --notify target given -> Alertmanager is still deployed (so alerts have "
            "somewhere to land and can be silenced/grouped), but with no receiver configured."
        )
        return NotifyConfig(kind=NOTIFY_KIND_NONE)

    for kind, pattern in NOTIFY_URL_PATTERNS:
        match = pattern.match(notify_url.strip())
        if match:
            decisions.append(
                f"Notification target recognised as a {NOTIFY_KIND_LABELS[kind]} -> "
                f"Alertmanager will deliver every firing alert there, grouped by alertname "
                "and severity."
            )
            return NotifyConfig(kind=kind, url=match.group("url"))

    warnings.append(
        f"Could not recognise --notify value {notify_url!r} as a Slack, Discord or HTTP "
        "webhook URL. No receiver was configured."
    )
    return NotifyConfig(kind=NOTIFY_KIND_NONE)


def _plan_install_mode(
    cpu_count: int, total_ram_gb: float, has_docker: bool, decisions: list[str], warnings: list[str]
) -> str:
    if not has_docker:
        decisions.append(
            "Docker was not detected on this host -> using binary installs (systemd units) "
            "downloaded from each project's official release."
        )
        return INSTALL_MODE_BINARY
    if cpu_count < BINARY_MODE_CPU_THRESHOLD or total_ram_gb < BINARY_MODE_RAM_GB_THRESHOLD:
        decisions.append(
            f"Host has {cpu_count} CPU(s) / {total_ram_gb:.0f}GB RAM (below {BINARY_MODE_CPU_THRESHOLD} "
            f"CPU / {BINARY_MODE_RAM_GB_THRESHOLD}GB) -> using binary installs instead of Docker to avoid "
            "the container runtime's own memory/CPU overhead on a resource-constrained server."
        )
        warnings.append(
            "This host is resource-constrained. signalpost will render systemd-based binary installs "
            "(install.sh) instead of docker-compose. Review install.sh before running it."
        )
        return INSTALL_MODE_BINARY
    decisions.append(
        f"Docker available and host has {cpu_count} CPU(s) / {total_ram_gb:.0f}GB RAM -> using "
        "docker-compose (simplest to operate and upgrade)."
    )
    return INSTALL_MODE_DOCKER


def _plan_prometheus_port(existing_prometheus: bool, decisions: list[str], warnings: list[str]) -> tuple[int, bool]:
    if existing_prometheus:
        warnings.append(
            f"An existing Prometheus container was detected. signalpost's Prometheus will bind to "
            f"{PROMETHEUS_CONFLICT_PORT} instead of {PROMETHEUS_DEFAULT_PORT} to avoid a port conflict."
        )
        decisions.append(
            f"Existing Prometheus container detected -> signalpost Prometheus moved to port "
            f"{PROMETHEUS_CONFLICT_PORT} (default {PROMETHEUS_DEFAULT_PORT} is taken)."
        )
        return PROMETHEUS_CONFLICT_PORT, True
    decisions.append(f"No existing Prometheus detected -> using default port {PROMETHEUS_DEFAULT_PORT}.")
    return PROMETHEUS_DEFAULT_PORT, False


def _plan_scrape_targets(services: list[Service], install_mode: str, decisions: list[str]) -> list[ScrapeTarget]:
    host = "localhost" if install_mode == INSTALL_MODE_BINARY else "host.docker.internal"
    targets: list[ScrapeTarget] = []
    for svc in services:
        targets.append(
            ScrapeTarget(
                job_name=svc.name,
                target=f"{host}:{svc.port_guess}",
                service=svc,
            )
        )
    if targets:
        decisions.append(
            f"Derived {len(targets)} scrape target(s) from detected services "
            f"({', '.join(t.job_name for t in targets)})."
        )
    else:
        decisions.append("No services detected -> no application scrape targets added (host-basics only).")
    return targets


def plan(detection: DetectionResult, notify_url: str | None = None) -> Plan:
    """Turn a :class:`DetectionResult` into a fully justified :class:`Plan`.

    ``notify_url`` is the optional ``--notify`` target (a Slack, Discord or
    generic HTTP webhook URL) that fired alerts should be delivered to.
    """
    decisions: list[str] = []
    warnings: list[str] = []

    retention = _plan_retention(detection.disk_free_gb, decisions, warnings)
    sampling_pct = _plan_sampling(len(detection.services), decisions)
    memory_limits = _plan_memory(detection.total_ram_gb, decisions)
    loki_ingest_mbps = _plan_loki_ingest(detection.total_ram_gb, decisions)
    alert_packages = _plan_alerts(detection.services, decisions)
    notify = _plan_notifications(notify_url, decisions, warnings)
    prometheus_port, prometheus_conflict = _plan_prometheus_port(
        detection.existing_prometheus, decisions, warnings
    )
    install_mode = _plan_install_mode(
        detection.cpu_count, detection.total_ram_gb, detection.has_docker, decisions, warnings
    )
    scrape_targets = _plan_scrape_targets(detection.services, install_mode, decisions)

    return Plan(
        log_retention_days=retention["log_days"],
        trace_retention_days=retention["trace_days"],
        metric_retention_days=retention["metric_days"],
        sampling_pct=sampling_pct,
        memory_limits=memory_limits,
        loki_ingest_mbps=loki_ingest_mbps,
        alert_packages=alert_packages,
        notify=notify,
        prometheus_port=prometheus_port,
        prometheus_port_conflict=prometheus_conflict,
        install_mode=install_mode,
        scrape_targets=scrape_targets,
        decisions=decisions,
        warnings=warnings,
    )
