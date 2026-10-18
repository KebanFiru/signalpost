"""Pinned component versions and their SHA-256 checksums.

GENERATED FILE - do not edit by hand.
Regenerate with: python scripts/update_versions.py

Every version here is paired with the checksum published by that exact
release. install.sh verifies each download against these values and aborts
on a mismatch, so a version bump that skips this script would break the
binary install mode loudly rather than silently weakening it.
"""

from __future__ import annotations

RELEASE_VERSIONS = {
    "prometheus": "3.13.2",
    "loki": "3.7.4",
    "tempo": "3.0.2",
    "grafana": "13.1.1",
    "otel_collector": "0.157.0",
    "node_exporter": "1.12.1",
    "alertmanager": "0.33.1",
}

DOCKER_IMAGES = {
    "prometheus": "prom/prometheus:v3.13.2",
    "loki": "grafana/loki:3.7.4",
    "tempo": "grafana/tempo:3.0.2",
    "grafana": "grafana/grafana:13.1.1",
    "otel_collector": "otel/opentelemetry-collector-contrib:0.157.0",
    "node_exporter": "prom/node-exporter:v1.12.1",
    "alertmanager": "prom/alertmanager:v0.33.1",
}

RELEASE_DOWNLOAD_URLS = {
    "prometheus": "https://github.com/prometheus/prometheus/releases/download/v{version}/prometheus-{version}.linux-{arch}.tar.gz",
    "loki": "https://github.com/grafana/loki/releases/download/v{version}/loki-linux-{arch}.zip",
    "tempo": "https://github.com/grafana/tempo/releases/download/v{version}/tempo_{version}_linux_{arch}.tar.gz",
    "grafana": "https://dl.grafana.com/oss/release/grafana-{version}.linux-{arch}.tar.gz",
    "otel_collector": "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v{version}/otelcol-contrib_{version}_linux_{arch}.tar.gz",
    "node_exporter": "https://github.com/prometheus/node_exporter/releases/download/v{version}/node_exporter-{version}.linux-{arch}.tar.gz",
    "alertmanager": "https://github.com/prometheus/alertmanager/releases/download/v{version}/alertmanager-{version}.linux-{arch}.tar.gz",
}

RELEASE_CHECKSUMS = {
    "prometheus": {
        "amd64": "0e8c4d46101bd025ea8265e377d2caabc57f488fc1be1c367f37db69ea41be6f",
        "arm64": "7cecb17a6f41d59814e1a0581a1f81f79051ad5973d1ecf39e23a9f747d6572a",
    },
    "loki": {
        "amd64": "4b4f17fc9416bd2099dac815ede1aac15aa0f8d1a21225e08909796b99aaad59",
        "arm64": "1c1db5709a8fef6c0e17f0e9bb1a9ddca2357de2f94f4c0d2cbd7085904d5904",
    },
    "tempo": {
        "amd64": "d2b95c01774c81c4494c4162e2f3511699a66b46506c96028745f5d4f0a78086",
        "arm64": "c58062096a87da26631be1ad941f7815378ca27b771eb789631313fffa998630",
    },
    "grafana": {
        "amd64": "0c07116968aea49768af8babd3c3f162d19012655a1a220cd7a9d97efe91da6c",
        "arm64": "8403dc0b5f50126fbe16d1a9c88f655823d104a8d9830335e572cd30dd0fffff",
    },
    "otel_collector": {
        "amd64": "d33177515a244a2393f03ffd66ab3e68a8fc11a56bc145ec4d0ca2644ee95504",
        "arm64": "34eb82390c462c877dd60ec5ec84de899088916facd07306ec988e4c34bd05b3",
    },
    "node_exporter": {
        "amd64": "b51d8a76aa2a9156a55d501aca6276fae09e262259a5e4e831d2c2222f084e63",
        "arm64": "ad35b605f9954b9f1ffddf5ba054bdc5a98d790b9eae5291e1eeb83f1ecbd0e7",
    },
    "alertmanager": {
        "amd64": "93d802cba6a8d27239d747ce117df7648d326ab67394e32247540b030e9842ba",
        "arm64": "50b32a346c3c29da411643dfa84990440e8fd03800380d7e664f22a863b7a0cf",
    },
}
