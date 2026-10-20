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
    "prometheus": "3.15.0",
    "loki": "3.7.8",
    "tempo": "3.1.0",
    "grafana": "13.2.4",
    "otel_collector": "0.163.1",
    "node_exporter": "1.12.1",
    "alertmanager": "0.34.1",
}

DOCKER_IMAGES = {
    "prometheus": "prom/prometheus:v3.15.0",
    "loki": "grafana/loki:3.7.8",
    "tempo": "grafana/tempo:3.1.0",
    "grafana": "grafana/grafana:13.2.4",
    "otel_collector": "otel/opentelemetry-collector-contrib:0.163.1",
    "node_exporter": "prom/node-exporter:v1.12.1",
    "alertmanager": "prom/alertmanager:v0.34.1",
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
        "amd64": "2a542df32eac02ee17b9d844fb2aa1de00dafa5476579ba8a3ba862e9d572ea0",
        "arm64": "f1f90ec08e849d494ca66c611470afc50192f0355f1a61c33f2cbde02d067823",
    },
    "loki": {
        "amd64": "62aea42c9cba52cd1642b3666ab37019a0ce4c24ab50b07e85dccc8d812f7d61",
        "arm64": "a874c10ffefe4d66c914b8aac8897159451d3026469598341aa03c76084697de",
    },
    "tempo": {
        "amd64": "9604ab46348270a42954801bba91cd65335e16568ef886bdf71b988fdcb7ac4e",
        "arm64": "e4092dcf2b93e141be77e300b539f6c5cceefa9803417d7d635c6797d9bc19ad",
    },
    "grafana": {
        "amd64": "c48765988fd88572607e4ea670251af8a8e64ab3e360d0f3cf67a6f3587b92ab",
        "arm64": "9517a0d21e2706b54521fbd720803698bba42859ca179e9905cc6b8fb05d67ab",
    },
    "otel_collector": {
        "amd64": "e93e6fd2b59427420a9e8eba5b9e78260df6d21e95283a7298084d2aa07f9df7",
        "arm64": "5ac4fb93e9858f6c7b5d5b2e81991dded61ca14b1a29bb01c3364e69567c76e3",
    },
    "node_exporter": {
        "amd64": "b51d8a76aa2a9156a55d501aca6276fae09e262259a5e4e831d2c2222f084e63",
        "arm64": "ad35b605f9954b9f1ffddf5ba054bdc5a98d790b9eae5291e1eeb83f1ecbd0e7",
    },
    "alertmanager": {
        "amd64": "265b9d1e55ef0d5306a436018af6d2b686c2ce051f03d968f7464ecb1372a7e8",
        "arm64": "d98d6cbaf52151c7e76e24355fec88b11cebcb9875d4cdd8b76ddce7a7e5535c",
    },
}
