from pathlib import Path

from signalpost.constants import (
    ALERTMANAGER_PORT,
    INSTALL_MODE_BINARY,
    INSTALL_MODE_DOCKER,
    LOKI_INGEST_MBPS_LOW,
    LOKI_INGEST_MBPS_NORMAL,
    MEMORY_LIMITS_HIGH,
    MEMORY_LIMITS_LOW,
    MEMORY_LIMITS_MID,
    NOTIFY_KIND_DISCORD,
    NOTIFY_KIND_NONE,
    NOTIFY_KIND_SLACK,
    NOTIFY_KIND_WEBHOOK,
    PROMETHEUS_CONFLICT_PORT,
    PROMETHEUS_DEFAULT_PORT,
    RETENTION_LARGE,
    RETENTION_MEDIUM,
    RETENTION_SMALL,
    SAMPLING_FULL_PCT,
    SAMPLING_HEAD_PCT,
)
from signalpost.models import DetectionResult, Service
from signalpost.planner import plan


def make_detection(
    disk_free_gb: float = 100.0,
    total_ram_gb: float = 16.0,
    services: list[Service] | None = None,
    existing_prometheus: bool = False,
    has_docker: bool = True,
    cpu_count: int = 4,
) -> DetectionResult:
    return DetectionResult(
        root=Path("."),
        has_docker=has_docker,
        has_kubectl=False,
        existing_compose_file=None,
        existing_prometheus=existing_prometheus,
        existing_grafana=False,
        services=services or [],
        cpu_count=cpu_count,
        total_ram_gb=total_ram_gb,
        disk_free_gb=disk_free_gb,
    )


def make_service(name: str, framework: str = "fastapi", language: str = "python", port: int = 8000) -> Service:
    return Service(name=name, language=language, framework=framework, path=Path(name), port_guess=port)


def test_retention_large_disk():
    p = plan(make_detection(disk_free_gb=150))
    assert p.log_retention_days == RETENTION_LARGE["log_days"]
    assert p.trace_retention_days == RETENTION_LARGE["trace_days"]
    assert p.metric_retention_days == RETENTION_LARGE["metric_days"]
    assert p.warnings == [
        "No notification target configured. Alerts will fire and group in Alertmanager "
        f"(:{ALERTMANAGER_PORT}) but will not reach anyone. Re-run with --notify "
        "<slack-or-discord-webhook-url> to route them."
    ]


def test_retention_medium_disk():
    p = plan(make_detection(disk_free_gb=50))
    assert p.log_retention_days == RETENTION_MEDIUM["log_days"]
    assert p.trace_retention_days == RETENTION_MEDIUM["trace_days"]
    assert p.metric_retention_days == RETENTION_MEDIUM["metric_days"]


def test_retention_small_disk_warns():
    p = plan(make_detection(disk_free_gb=10))
    assert p.log_retention_days == RETENTION_SMALL["log_days"]
    assert p.trace_retention_days == RETENTION_SMALL["trace_days"]
    assert p.metric_retention_days == RETENTION_SMALL["metric_days"]
    assert any("disk" in w.lower() for w in p.warnings)


def test_retention_boundary_at_100gb_is_large_tier():
    p = plan(make_detection(disk_free_gb=100))
    assert p.log_retention_days == RETENTION_LARGE["log_days"]


def test_retention_boundary_at_40gb_is_medium_tier():
    p = plan(make_detection(disk_free_gb=40))
    assert p.log_retention_days == RETENTION_MEDIUM["log_days"]


def test_retention_just_below_40gb_is_small_tier():
    p = plan(make_detection(disk_free_gb=39.9))
    assert p.log_retention_days == RETENTION_SMALL["log_days"]


def test_sampling_full_at_or_below_five_services():
    services = [make_service(f"svc{i}") for i in range(5)]
    p = plan(make_detection(services=services))
    assert p.sampling_pct == SAMPLING_FULL_PCT


def test_sampling_head_above_five_services():
    services = [make_service(f"svc{i}") for i in range(6)]
    p = plan(make_detection(services=services))
    assert p.sampling_pct == SAMPLING_HEAD_PCT


def test_sampling_zero_services_is_full():
    p = plan(make_detection(services=[]))
    assert p.sampling_pct == SAMPLING_FULL_PCT


def test_memory_high_tier():
    p = plan(make_detection(total_ram_gb=32))
    assert p.memory_limits == MEMORY_LIMITS_HIGH


def test_memory_mid_tier():
    p = plan(make_detection(total_ram_gb=8))
    assert p.memory_limits == MEMORY_LIMITS_MID


def test_memory_low_tier():
    p = plan(make_detection(total_ram_gb=4))
    assert p.memory_limits == MEMORY_LIMITS_LOW


def test_memory_boundary_16gb_is_high():
    p = plan(make_detection(total_ram_gb=16))
    assert p.memory_limits == MEMORY_LIMITS_HIGH


def test_memory_just_below_8gb_is_low():
    p = plan(make_detection(total_ram_gb=7.9))
    assert p.memory_limits == MEMORY_LIMITS_LOW


def test_loki_ingest_normal_at_8gb_ram():
    p = plan(make_detection(total_ram_gb=8))
    assert p.loki_ingest_mbps == LOKI_INGEST_MBPS_NORMAL


def test_loki_ingest_low_below_8gb_ram():
    p = plan(make_detection(total_ram_gb=4))
    assert p.loki_ingest_mbps == LOKI_INGEST_MBPS_LOW


def test_alerts_always_include_host_basics_and_selfhealth():
    p = plan(make_detection(services=[]))
    assert "host-basics" in p.alert_packages
    assert "stack-selfhealth" in p.alert_packages
    assert "http-red" not in p.alert_packages


def test_alerts_include_http_red_for_python_web_service():
    p = plan(make_detection(services=[make_service("api", framework="fastapi")]))
    assert "http-red" in p.alert_packages


def test_alerts_no_http_red_for_non_web_python_service():
    p = plan(make_detection(services=[make_service("worker", framework="python")]))
    assert "http-red" not in p.alert_packages


def test_alerts_http_red_for_flask_and_django_too():
    for fw in ("flask", "django"):
        p = plan(make_detection(services=[make_service("api", framework=fw)]))
        assert "http-red" in p.alert_packages


def test_alerts_slo_burn_rate_follows_http_red():
    p = plan(make_detection(services=[make_service("api", framework="fastapi")]))
    assert "slo-burn-rate" in p.alert_packages


def test_alerts_no_slo_burn_rate_without_http_red():
    p = plan(make_detection(services=[]))
    assert "slo-burn-rate" not in p.alert_packages


def test_install_mode_docker_when_available_and_resourced():
    p = plan(make_detection(has_docker=True, cpu_count=4, total_ram_gb=16))
    assert p.install_mode == INSTALL_MODE_DOCKER


def test_install_mode_binary_when_docker_missing():
    p = plan(make_detection(has_docker=False))
    assert p.install_mode == INSTALL_MODE_BINARY
    assert any("docker" in w.lower() for w in p.decisions)


def test_install_mode_binary_when_cpu_constrained():
    p = plan(make_detection(has_docker=True, cpu_count=1, total_ram_gb=16))
    assert p.install_mode == INSTALL_MODE_BINARY
    assert any("resource-constrained" in w.lower() for w in p.warnings)


def test_install_mode_binary_when_ram_constrained():
    p = plan(make_detection(has_docker=True, cpu_count=4, total_ram_gb=2))
    assert p.install_mode == INSTALL_MODE_BINARY


def test_install_mode_docker_at_threshold_boundary():
    p = plan(make_detection(has_docker=True, cpu_count=2, total_ram_gb=4))
    assert p.install_mode == INSTALL_MODE_DOCKER


def test_prometheus_default_port_when_no_conflict():
    p = plan(make_detection(existing_prometheus=False))
    assert p.prometheus_port == PROMETHEUS_DEFAULT_PORT
    assert not p.prometheus_port_conflict


def test_prometheus_alternate_port_on_conflict():
    p = plan(make_detection(existing_prometheus=True))
    assert p.prometheus_port == PROMETHEUS_CONFLICT_PORT
    assert p.prometheus_port_conflict
    assert any("prometheus" in w.lower() for w in p.warnings)


def test_scrape_targets_derived_from_services():
    services = [
        make_service("api", port=8000),
        make_service("web", language="javascript", framework="express", port=3000),
    ]
    p = plan(make_detection(services=services))
    assert len(p.scrape_targets) == 2
    targets = {t.job_name: t.target for t in p.scrape_targets}
    assert targets["api"] == "host.docker.internal:8000"
    assert targets["web"] == "host.docker.internal:3000"


def test_no_scrape_targets_without_services():
    p = plan(make_detection(services=[]))
    assert p.scrape_targets == []


def test_scrape_targets_use_localhost_in_binary_mode():
    services = [make_service("api", port=8000)]
    p = plan(make_detection(services=services, has_docker=False))
    assert p.install_mode == INSTALL_MODE_BINARY
    assert p.scrape_targets[0].target == "localhost:8000"


def test_decisions_are_populated():
    p = plan(make_detection())
    assert len(p.decisions) >= 5
    assert all(isinstance(d, str) and d for d in p.decisions)


def test_notify_missing_warns_and_defaults_to_none():
    p = plan(make_detection())
    assert p.notify.kind == NOTIFY_KIND_NONE
    assert not p.notify.configured
    assert any("will not reach anyone" in w for w in p.warnings)


def test_notify_slack_webhook_recognised():
    url = "https://hooks.slack.com/services/T00/B00/xxx"
    p = plan(make_detection(), notify_url=url)
    assert p.notify.kind == NOTIFY_KIND_SLACK
    assert p.notify.url == url
    assert p.notify.configured
    assert not any("will not reach anyone" in w for w in p.warnings)


def test_notify_slack_scheme_prefix_recognised():
    p = plan(make_detection(), notify_url="slack://https://hooks.slack.com/services/T00/B00/xxx")
    assert p.notify.kind == NOTIFY_KIND_SLACK
    assert p.notify.url == "https://hooks.slack.com/services/T00/B00/xxx"


def test_notify_discord_webhook_recognised():
    url = "https://discord.com/api/webhooks/123/abc"
    p = plan(make_detection(), notify_url=url)
    assert p.notify.kind == NOTIFY_KIND_DISCORD
    assert p.notify.url == url


def test_notify_generic_https_falls_back_to_webhook():
    url = "https://example.com/hooks/alerts"
    p = plan(make_detection(), notify_url=url)
    assert p.notify.kind == NOTIFY_KIND_WEBHOOK
    assert p.notify.url == url


def test_notify_unrecognised_value_warns():
    p = plan(make_detection(), notify_url="not-a-url")
    assert p.notify.kind == NOTIFY_KIND_NONE
    assert any("Could not recognise" in w for w in p.warnings)
