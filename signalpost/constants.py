from __future__ import annotations

import re
from pathlib import Path

from signalpost.versions import DOCKER_IMAGES as DOCKER_IMAGES
from signalpost.versions import RELEASE_CHECKSUMS as RELEASE_CHECKSUMS
from signalpost.versions import RELEASE_DOWNLOAD_URLS as RELEASE_DOWNLOAD_URLS
from signalpost.versions import RELEASE_VERSIONS as RELEASE_VERSIONS

SKIP_DIRS = {"node_modules", ".git", ".venv", "venv", "__pycache__", ".tox", "dist", "build"}
MAX_DEPTH = 2

COMPOSE_FILE_CANDIDATES = [
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
]

PROMETHEUS_CONTAINER_KEYWORDS = ("prometheus",)
GRAFANA_CONTAINER_KEYWORDS = ("grafana",)

PORT_GUESS_FILE_CANDIDATES = [
    "main.py",
    "app.py",
    "server.py",
    "index.js",
    "app.js",
    "server.js",
    ".env",
]

PORT_PATTERNS = [
    re.compile(r"PORT\s*[:=]\s*[\"']?(\d{2,5})"),
    re.compile(r"port\s*[:=]\s*[\"']?(\d{2,5})"),
    re.compile(r"listen\(\s*(\d{2,5})"),
    re.compile(r"run\([^)]*port\s*=\s*(\d{2,5})"),
    re.compile(r"uvicorn\.run\([^)]*port\s*=\s*(\d{2,5})"),
]

DEFAULT_PORTS = {
    "fastapi": 8000,
    "flask": 5000,
    "django": 8000,
    "express": 3000,
    "fastify": 3000,
    "koa": 3000,
}
FALLBACK_PORT = 8080

DISK_TIER_LARGE_GB = 100
DISK_TIER_MEDIUM_GB = 40

RETENTION_LARGE = {"log_days": 14, "trace_days": 7, "metric_days": 30}
RETENTION_MEDIUM = {"log_days": 7, "trace_days": 3, "metric_days": 15}
RETENTION_SMALL = {"log_days": 3, "trace_days": 1, "metric_days": 7}

SAMPLING_SERVICE_THRESHOLD = 5
SAMPLING_FULL_PCT = 100
SAMPLING_HEAD_PCT = 25

RAM_TIER_HIGH_GB = 16
RAM_TIER_MID_GB = 8

MEMORY_LIMITS_HIGH = {
    "grafana_mb": 512,
    "loki_mb": 1024,
    "tempo_mb": 1024,
    "prometheus_mb": 1024,
    "otel_collector_mb": 512,
    "alertmanager_mb": 128,
}
MEMORY_LIMITS_MID = {
    "grafana_mb": 256,
    "loki_mb": 512,
    "tempo_mb": 512,
    "prometheus_mb": 512,
    "otel_collector_mb": 256,
    "alertmanager_mb": 96,
}
MEMORY_LIMITS_LOW = {
    "grafana_mb": 128,
    "loki_mb": 256,
    "tempo_mb": 256,
    "prometheus_mb": 256,
    "otel_collector_mb": 128,
    "alertmanager_mb": 64,
}

LOKI_INGEST_MBPS_NORMAL = 8
LOKI_INGEST_MBPS_LOW = 4

PROMETHEUS_DEFAULT_PORT = 9090
PROMETHEUS_CONFLICT_PORT = 9091

ALERTMANAGER_PORT = 9093

NOTIFY_KIND_SLACK = "slack"
NOTIFY_KIND_DISCORD = "discord"
NOTIFY_KIND_WEBHOOK = "webhook"
NOTIFY_KIND_NONE = "none"

NOTIFY_URL_PATTERNS = (
    (NOTIFY_KIND_SLACK, re.compile(r"^slack://(?P<url>.+)$", re.IGNORECASE)),
    (NOTIFY_KIND_DISCORD, re.compile(r"^discord://(?P<url>.+)$", re.IGNORECASE)),
    (NOTIFY_KIND_WEBHOOK, re.compile(r"^webhook://(?P<url>.+)$", re.IGNORECASE)),
    (NOTIFY_KIND_SLACK, re.compile(r"^(?P<url>https://hooks\.slack\.com/.+)$", re.IGNORECASE)),
    (
        NOTIFY_KIND_DISCORD,
        re.compile(r"^(?P<url>https://(?:\w+\.)?discord(?:app)?\.com/api/webhooks/.+)$", re.IGNORECASE),
    ),
    (NOTIFY_KIND_WEBHOOK, re.compile(r"^(?P<url>https?://.+)$", re.IGNORECASE)),
)

NOTIFY_KIND_LABELS = {
    NOTIFY_KIND_SLACK: "Slack incoming webhook",
    NOTIFY_KIND_DISCORD: "Discord webhook",
    NOTIFY_KIND_WEBHOOK: "generic HTTP webhook",
    NOTIFY_KIND_NONE: "no notification target",
}

ALERTMANAGER_GROUP_WAIT = "30s"
ALERTMANAGER_GROUP_INTERVAL = "5m"
ALERTMANAGER_REPEAT_INTERVAL = "4h"
ALERTMANAGER_CRITICAL_REPEAT_INTERVAL = "1h"

INSTALL_MODE_DOCKER = "docker"
INSTALL_MODE_BINARY = "binary"

BINARY_MODE_CPU_THRESHOLD = 2
BINARY_MODE_RAM_GB_THRESHOLD = 4

ARCH_AMD64 = "amd64"
ARCH_ARM64 = "arm64"
ARCH_ALIASES = {
    "x86_64": ARCH_AMD64,
    "amd64": ARCH_AMD64,
    "aarch64": ARCH_ARM64,
    "arm64": ARCH_ARM64,
}

BINARY_INSTALL_ROOT = "/opt/signalpost"
BINARY_SYSTEMD_USER = "signalpost"

TEMPLATES_DIR = Path(__file__).parent / "templates"
OUTPUT_DIRNAME = "observability"
SECRETS_DIRNAME = "secrets"
GRAFANA_PASSWORD_FILENAME = "grafana_admin_password.txt"
PASSWORD_LENGTH = 24

STATE_FILENAME = ".signalpost-state.json"

ALERTMANAGER_WEBHOOK_SECRET_NAME = "alertmanager_webhook_url"
ALERTMANAGER_WEBHOOK_FILENAME = "alertmanager_webhook_url.txt"

COMMON_TEMPLATE_MAP = {
    "provisioning/datasources/datasources.yml.j2": "provisioning/datasources/datasources.yml",
    "provisioning/dashboards/dashboards.yml.j2": "provisioning/dashboards/dashboards.yml",
    "provisioning/dashboards/host-basics.json": "provisioning/dashboards/host-basics.json",
    "provisioning/dashboards/stack-selfhealth.json": "provisioning/dashboards/stack-selfhealth.json",
    "configs/loki-config.yml.j2": "configs/loki-config.yml",
    "configs/tempo-config.yml.j2": "configs/tempo-config.yml",
    "configs/prometheus.yml.j2": "configs/prometheus.yml",
    "configs/otel-collector-config.yml.j2": "configs/otel-collector-config.yml",
    "configs/alertmanager.yml.j2": "configs/alertmanager.yml",
}

DOCKER_TEMPLATE_MAP = {
    "compose/docker-compose.signalpost.yml.j2": "docker-compose.signalpost.yml",
}

BINARY_TEMPLATE_MAP = {
    "binary/install.sh.j2": "install.sh",
}

ALERT_TEMPLATE_MAP = {
    "host-basics": "alerts/host-basics.yml",
    "stack-selfhealth": "alerts/stack-selfhealth.yml",
    "http-red": "alerts/http-red.yml.j2",
    "slo-burn-rate": "alerts/slo-burn-rate.yml.j2",
}
ALERT_OUTPUT_MAP = {
    "host-basics": "alerts/host-basics.yml",
    "stack-selfhealth": "alerts/stack-selfhealth.yml",
    "http-red": "alerts/http-red.yml",
    "slo-burn-rate": "alerts/slo-burn-rate.yml",
}

CONDITIONAL_DASHBOARD_TEMPLATE_MAP = {
    "http-red": ("provisioning/dashboards/http-red.json.j2", "provisioning/dashboards/http-red.json"),
}

SLO_TARGET_PCT = 99.9
SLO_FAST_BURN_RATE = 14.4
SLO_SLOW_BURN_RATE = 6.0

OTLP_ENDPOINT = "localhost:4317"

ENTRY_FILE_CANDIDATES = ("main.py", "app.py", "server.py")

REQUIRED_PACKAGES = [
    "opentelemetry-distro",
    "opentelemetry-exporter-otlp",
    "opentelemetry-instrumentation-fastapi",
    "opentelemetry-instrumentation-logging",
]

APP_CREATION_PATTERN = re.compile(r"^(\w+)\s*=\s*FastAPI\(", re.MULTILINE)
ALREADY_INSTRUMENTED_MARKER = "# signalpost: otel instrumentation"

IMPORT_SNIPPET_TEMPLATE = '''{marker}
import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

_resource = Resource.create({{SERVICE_NAME: "{service_name}"}})
_tracer_provider = TracerProvider(resource=_resource)
_tracer_provider.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="{otlp_endpoint}", insecure=True))
)
trace.set_tracer_provider(_tracer_provider)

LoggingInstrumentor().instrument(set_logging_format=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [trace_id=%(otelTraceID)s span_id=%(otelSpanID)s] %(name)s: %(message)s",
)
'''

INSTRUMENT_CALL_TEMPLATE = "FastAPIInstrumentor.instrument_app({app_var})  {marker}\n"

ALERT_PACKAGE_DESCRIPTIONS = {
    "host-basics": "CPU / RAM / disk / node-exporter availability",
    "stack-selfhealth": "signalpost component uptime, Loki ingest errors, collector queue health",
    "http-red": "HTTP Rate / Errors / Duration for detected Python web services",
    "slo-burn-rate": "Google SRE-style multi-window multi-burn-rate SLO alerts",
}

DASHBOARD_NAMES = ("host-basics", "stack-selfhealth", "http-red")

DASHBOARD_DESCRIPTIONS = {
    "host-basics": "CPU, memory, disk and network for the host",
    "stack-selfhealth": "Up/down status of every signalpost component",
    "http-red": "Rate / Errors / Duration for detected web services, with log+trace correlation",
}
