import json
from pathlib import Path

from signalpost.constants import INSTALL_MODE_BINARY, INSTALL_MODE_DOCKER, STATE_FILENAME
from signalpost.deploy import deploy
from signalpost.models import DetectionResult
from signalpost.planner import plan


def make_detection(
    disk_free_gb: float = 100.0,
    total_ram_gb: float = 16.0,
    has_docker: bool = True,
    cpu_count: int = 4,
    root: Path | None = None,
) -> DetectionResult:
    return DetectionResult(
        root=root or Path("."),
        has_docker=has_docker,
        has_kubectl=False,
        existing_compose_file=None,
        existing_prometheus=False,
        existing_grafana=False,
        services=[],
        cpu_count=cpu_count,
        total_ram_gb=total_ram_gb,
        disk_free_gb=disk_free_gb,
    )


def test_binary_mode_collector_config_uses_localhost_not_docker_service_names(tmp_path):
    """Regression test for the collector silently dropping every pipeline in
    binary mode: its exporters must resolve against `localhost`/the plan's
    own port, not the Docker Compose service names (`tempo`, `loki`,
    `prometheus`) that don't exist as DNS names under systemd."""
    detection = make_detection(root=tmp_path, has_docker=False, cpu_count=1, total_ram_gb=2.0)
    result_plan = plan(detection)
    assert result_plan.install_mode == INSTALL_MODE_BINARY

    deploy(result_plan, detection, output_dir=tmp_path / "observability")
    config = (tmp_path / "observability" / "configs" / "otel-collector-config.yml").read_text()

    assert "tempo:4317" not in config
    assert "loki:3100" not in config
    assert "prometheus:9090" not in config
    assert f"localhost:{result_plan.prometheus_port}/api/v1/write" in config
    assert "localhost:4317" in config
    assert "http://localhost:3100/otlp" in config


def test_docker_mode_collector_config_uses_docker_service_names(tmp_path):
    detection = make_detection(root=tmp_path, has_docker=True, cpu_count=4, total_ram_gb=16.0)
    result_plan = plan(detection)
    assert result_plan.install_mode == INSTALL_MODE_DOCKER

    deploy(result_plan, detection, output_dir=tmp_path / "observability")
    config = (tmp_path / "observability" / "configs" / "otel-collector-config.yml").read_text()

    assert "tempo:4317" in config
    assert "http://loki:3100/otlp" in config
    assert "http://prometheus:9090/api/v1/write" in config


def test_http_red_dashboard_only_written_when_package_enabled(tmp_path):
    detection = make_detection(root=tmp_path)
    result_plan = plan(detection)
    result_plan.alert_packages = ["host-basics", "stack-selfhealth"]

    deploy(result_plan, detection, output_dir=tmp_path / "observability")

    assert (tmp_path / "observability" / "provisioning" / "dashboards" / "host-basics.json").exists()
    assert not (tmp_path / "observability" / "provisioning" / "dashboards" / "http-red.json").exists()


def test_http_red_dashboard_written_when_package_enabled(tmp_path):
    detection = make_detection(root=tmp_path)
    result_plan = plan(detection)
    result_plan.alert_packages = ["host-basics", "stack-selfhealth", "http-red", "slo-burn-rate"]

    deploy(result_plan, detection, output_dir=tmp_path / "observability")

    assert (tmp_path / "observability" / "provisioning" / "dashboards" / "http-red.json").exists()


def test_state_file_records_versions_and_file_hashes_without_secrets(tmp_path):
    detection = make_detection(root=tmp_path)
    result_plan = plan(detection)
    result_plan.notify.kind = "slack"
    result_plan.notify.url = "https://hooks.slack.com/services/super-secret-token"

    deploy(result_plan, detection, output_dir=tmp_path / "observability")
    state = json.loads((tmp_path / "observability" / STATE_FILENAME).read_text())

    assert state["signalpost_version"]
    assert state["component_versions"]["prometheus"]
    assert state["plan"]["install_mode"] == INSTALL_MODE_DOCKER
    assert state["plan"]["notify_kind"] == "slack"
    assert "url" not in state["plan"]
    assert "super-secret-token" not in json.dumps(state)
    assert len(state["files"]) > 0
    for digest in state["files"].values():
        assert len(digest) == 64


def test_redeploy_with_unchanged_content_creates_no_backups(tmp_path):
    detection = make_detection(root=tmp_path)
    result_plan = plan(detection)
    output_dir = tmp_path / "observability"

    deploy(result_plan, detection, output_dir=output_dir)
    second = deploy(result_plan, detection, output_dir=output_dir)

    assert second.backed_up == []


def test_redeploy_after_hand_edit_creates_timestamped_backup(tmp_path):
    detection = make_detection(root=tmp_path)
    result_plan = plan(detection)
    output_dir = tmp_path / "observability"

    deploy(result_plan, detection, output_dir=output_dir)
    compose_path = output_dir / "docker-compose.signalpost.yml"
    original_content = compose_path.read_text()
    compose_path.write_text(original_content + "\n# hand-edited\n")

    result = deploy(result_plan, detection, output_dir=output_dir)

    backup_names = [f.name for f in result.backed_up]
    matches = [n for n in backup_names if n.startswith("docker-compose.signalpost.yml.bak.")]
    assert len(matches) == 1
    assert (output_dir / matches[0]).read_text() == original_content + "\n# hand-edited\n"
    assert compose_path.read_text() == original_content
