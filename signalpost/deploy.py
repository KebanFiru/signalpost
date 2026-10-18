"""Render signalpost's Jinja2 templates and write the observability stack to disk."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import stat
import string
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from signalpost import __version__
from signalpost.constants import (
    ALERT_OUTPUT_MAP,
    ALERT_TEMPLATE_MAP,
    ALERTMANAGER_CRITICAL_REPEAT_INTERVAL,
    ALERTMANAGER_GROUP_INTERVAL,
    ALERTMANAGER_GROUP_WAIT,
    ALERTMANAGER_PORT,
    ALERTMANAGER_REPEAT_INTERVAL,
    ALERTMANAGER_WEBHOOK_FILENAME,
    ALERTMANAGER_WEBHOOK_SECRET_NAME,
    BINARY_INSTALL_ROOT,
    BINARY_SYSTEMD_USER,
    BINARY_TEMPLATE_MAP,
    COMMON_TEMPLATE_MAP,
    CONDITIONAL_DASHBOARD_TEMPLATE_MAP,
    DOCKER_IMAGES,
    DOCKER_TEMPLATE_MAP,
    GRAFANA_PASSWORD_FILENAME,
    INSTALL_MODE_BINARY,
    INSTALL_MODE_DOCKER,
    OUTPUT_DIRNAME,
    PASSWORD_LENGTH,
    RELEASE_CHECKSUMS,
    RELEASE_DOWNLOAD_URLS,
    RELEASE_VERSIONS,
    SECRETS_DIRNAME,
    SLO_FAST_BURN_RATE,
    SLO_SLOW_BURN_RATE,
    SLO_TARGET_PCT,
    STATE_FILENAME,
    TEMPLATES_DIR,
)
from signalpost.models import DeployResult, DetectionResult, Plan


def _make_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATES_DIR)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def _generate_password(length: int = PASSWORD_LENGTH) -> str:
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _resolve_release_urls(arch: str) -> dict[str, str]:
    return {name: url.format(version=RELEASE_VERSIONS[name], arch=arch) for name, url in RELEASE_DOWNLOAD_URLS.items()}


def _resolve_release_checksums(arch: str) -> dict[str, str]:
    return {name: checksums[arch] for name, checksums in RELEASE_CHECKSUMS.items()}


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _backup_if_exists(path: Path, new_content: str, result: DeployResult) -> None:
    """Back up ``path`` before it's overwritten with ``new_content``.

    Skips the backup entirely when the on-disk content is byte-identical to
    what's about to be written — a no-op deploy shouldn't churn out backup
    files. When content *does* differ, the backup gets a UTC timestamp
    suffix rather than a single reused ``.bak``: a plain ``.bak`` gets
    silently clobbered by a second deploy, which loses the original for
    good. Timestamping means every prior version is still on disk somewhere.
    """
    if not path.exists():
        return
    existing = path.read_bytes()
    if existing == new_content.encode("utf-8"):
        return
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = path.with_name(f"{path.name}.bak.{timestamp}")
    result.backed_up.append(backup_path)
    if result.dry_run:
        return
    backup_path.write_bytes(existing)


def _write_rendered(path: Path, content: str, result: DeployResult) -> None:
    _backup_if_exists(path, content, result)
    result.written.append(path)
    result.file_hashes[path.relative_to(result.output_dir).as_posix()] = _hash_content(content)
    if result.dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_secret(path: Path, content: str, result: DeployResult) -> None:
    _backup_if_exists(path, content, result)
    result.written.append(path)
    if result.dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH)
    except Exception:
        pass


def _plan_state_summary(plan: Plan) -> dict:
    """The subset of ``plan`` worth recording in STATE_FILENAME.

    Deliberately excludes ``plan.notify.url`` (a webhook secret),
    ``plan.scrape_targets`` (derived, regenerable from a fresh ``detect()``),
    and ``plan.decisions``/``plan.warnings`` (human-readable text, not state).
    """
    return {
        "log_retention_days": plan.log_retention_days,
        "trace_retention_days": plan.trace_retention_days,
        "metric_retention_days": plan.metric_retention_days,
        "sampling_pct": plan.sampling_pct,
        "memory_limits": plan.memory_limits,
        "loki_ingest_mbps": plan.loki_ingest_mbps,
        "alert_packages": plan.alert_packages,
        "notify_kind": plan.notify.kind,
        "prometheus_port": plan.prometheus_port,
        "install_mode": plan.install_mode,
    }


def _write_state_file(plan: Plan, output_dir: Path, result: DeployResult) -> None:
    state = {
        "signalpost_version": __version__,
        "deployed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "component_versions": RELEASE_VERSIONS,
        "plan": _plan_state_summary(plan),
        "files": dict(sorted(result.file_hashes.items())),
    }
    content = json.dumps(state, indent=2, sort_keys=True) + "\n"
    path = output_dir / STATE_FILENAME
    _backup_if_exists(path, content, result)
    result.written.append(path)
    if result.dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def deploy(
    plan: Plan,
    detection: DetectionResult,
    output_dir: Path | None = None,
    dry_run: bool = False,
) -> DeployResult:
    """Render every template for ``plan``/``detection`` under ``output_dir``.

    ``output_dir`` defaults to ``<detection.root>/observability``. Existing
    files whose content is about to change are backed up to
    ``<name>.bak.<UTC timestamp>`` before being overwritten (unchanged files
    are left alone, and no backup is a lost overwrite of a prior one — each
    deploy gets its own backup file). A ``STATE_FILENAME`` manifest is
    written alongside the stack recording the signalpost/component versions,
    the plan's decisions, and a sha256 per rendered file. In dry-run mode
    nothing is written to disk, but the result still reports what *would*
    have been written/backed up.
    """
    output_dir = (output_dir or detection.root / OUTPUT_DIRNAME).resolve()
    result = DeployResult(output_dir=output_dir, dry_run=dry_run)

    if plan.install_mode == INSTALL_MODE_DOCKER:
        alertmanager_webhook_secret_path = f"/run/secrets/{ALERTMANAGER_WEBHOOK_SECRET_NAME}"
    else:
        alertmanager_webhook_secret_path = (
            f"{output_dir.as_posix()}/{SECRETS_DIRNAME}/{ALERTMANAGER_WEBHOOK_FILENAME}"
        )

    env = _make_env()
    context = {
        "plan": plan,
        "detection": detection,
        "output_dir": output_dir,
        "output_dir_posix": output_dir.as_posix(),
        "release_urls": _resolve_release_urls(detection.arch),
        "release_versions": RELEASE_VERSIONS,
        "release_checksums": _resolve_release_checksums(detection.arch),
        "docker_images": DOCKER_IMAGES,
        "install_root": BINARY_INSTALL_ROOT,
        "systemd_user": BINARY_SYSTEMD_USER,
        "grafana_password_filename": GRAFANA_PASSWORD_FILENAME,
        "slo_target_pct": SLO_TARGET_PCT,
        "slo_fast_burn_rate": SLO_FAST_BURN_RATE,
        "slo_slow_burn_rate": SLO_SLOW_BURN_RATE,
        "alertmanager_port": ALERTMANAGER_PORT,
        "alertmanager_group_wait": ALERTMANAGER_GROUP_WAIT,
        "alertmanager_group_interval": ALERTMANAGER_GROUP_INTERVAL,
        "alertmanager_repeat_interval": ALERTMANAGER_REPEAT_INTERVAL,
        "alertmanager_critical_repeat_interval": ALERTMANAGER_CRITICAL_REPEAT_INTERVAL,
        "alertmanager_webhook_secret_name": ALERTMANAGER_WEBHOOK_SECRET_NAME,
        "alertmanager_webhook_filename": ALERTMANAGER_WEBHOOK_FILENAME,
        "alertmanager_webhook_secret_path": alertmanager_webhook_secret_path,
    }

    def _render_or_copy(template_rel: str) -> str:
        if template_rel.endswith(".j2"):
            template = env.get_template(template_rel.replace(os.sep, "/"))
            return template.render(**context)
        return (TEMPLATES_DIR / template_rel).read_text(encoding="utf-8")

    for template_rel, output_rel in COMMON_TEMPLATE_MAP.items():
        rendered = _render_or_copy(template_rel)
        _write_rendered(output_dir / output_rel, rendered, result)

    mode_template_map = DOCKER_TEMPLATE_MAP if plan.install_mode == INSTALL_MODE_DOCKER else BINARY_TEMPLATE_MAP
    for template_rel, output_rel in mode_template_map.items():
        rendered = _render_or_copy(template_rel)
        dest = output_dir / output_rel
        _write_rendered(dest, rendered, result)
        if plan.install_mode == INSTALL_MODE_BINARY and not dry_run:
            os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    for package in plan.alert_packages:
        template_rel = ALERT_TEMPLATE_MAP.get(package)
        output_rel = ALERT_OUTPUT_MAP.get(package)
        if not template_rel or not output_rel:
            result.warnings.append(f"Unknown alert package '{package}' — skipped.")
            continue
        rendered = _render_or_copy(template_rel)
        _write_rendered(output_dir / output_rel, rendered, result)

        dashboard = CONDITIONAL_DASHBOARD_TEMPLATE_MAP.get(package)
        if dashboard:
            dashboard_template_rel, dashboard_output_rel = dashboard
            rendered = _render_or_copy(dashboard_template_rel)
            _write_rendered(output_dir / dashboard_output_rel, rendered, result)

    secret_path = output_dir / SECRETS_DIRNAME / GRAFANA_PASSWORD_FILENAME
    if secret_path.exists():
        result.grafana_password_file = secret_path
        result.warnings.append(
            f"{secret_path} already exists — keeping existing Grafana admin password."
        )
    else:
        password = _generate_password()
        _write_secret(secret_path, password + "\n", result)
        result.grafana_password_file = secret_path

    if plan.notify.configured:
        webhook_secret_path = output_dir / SECRETS_DIRNAME / ALERTMANAGER_WEBHOOK_FILENAME
        _write_secret(webhook_secret_path, plan.notify.url + "\n", result)

    _write_state_file(plan, output_dir, result)

    return result
