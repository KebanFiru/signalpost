#!/usr/bin/env python3
"""Regenerate signalpost/versions.py from upstream releases.

signalpost pins an exact version *and* an exact SHA-256 for every component it
installs. Both have to come from the same place at the same time, or the pin
is worthless. This script fetches the latest release of each component, pulls
the checksum straight out of that release's own checksum artifact, and writes
signalpost/versions.py.

Usage:
    python scripts/update_versions.py            # latest of everything
    python scripts/update_versions.py --check    # report drift, write nothing
    python scripts/update_versions.py --pin loki=3.7.4

Requires network access. Uses only the standard library so it can run in CI
without installing anything.

Exit codes: 0 success/up-to-date, 1 drift detected (`--check` only), 2 unknown
`--pin` component, 3 a fetch failed (network error, bad release data) — this
is distinct from 1 so callers like CI don't mistake a transient API failure
for real version drift.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = REPO_ROOT / "signalpost" / "versions.py"

ARCHES = ("amd64", "arm64")

COMPONENTS = {
    "prometheus": {
        "repo": "prometheus/prometheus",
        "url": "https://github.com/prometheus/prometheus/releases/download/v{version}/prometheus-{version}.linux-{arch}.tar.gz",
        "artifact": "prometheus-{version}.linux-{arch}.tar.gz",
        "checksums": "https://github.com/prometheus/prometheus/releases/download/v{version}/sha256sums.txt",
    },
    "loki": {
        "repo": "grafana/loki",
        "url": "https://github.com/grafana/loki/releases/download/v{version}/loki-linux-{arch}.zip",
        "artifact": "loki-linux-{arch}.zip",
        "checksums": "https://github.com/grafana/loki/releases/download/v{version}/SHA256SUMS",
    },
    "tempo": {
        "repo": "grafana/tempo",
        "url": "https://github.com/grafana/tempo/releases/download/v{version}/tempo_{version}_linux_{arch}.tar.gz",
        "artifact": "tempo_{version}_linux_{arch}.tar.gz",
        "checksums": "https://github.com/grafana/tempo/releases/download/v{version}/SHA256SUMS",
    },
    "grafana": {
        "repo": "grafana/grafana",
        "url": "https://dl.grafana.com/oss/release/grafana-{version}.linux-{arch}.tar.gz",
        "artifact": "grafana-{version}.linux-{arch}.tar.gz",
        "checksums": "https://dl.grafana.com/oss/release/grafana-{version}.linux-{arch}.tar.gz.sha256",
        "checksum_per_arch": True,
    },
    "otel_collector": {
        "repo": "open-telemetry/opentelemetry-collector-releases",
        "url": "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v{version}/otelcol-contrib_{version}_linux_{arch}.tar.gz",
        "artifact": "otelcol-contrib_{version}_linux_{arch}.tar.gz",
        "checksums": "https://github.com/open-telemetry/opentelemetry-collector-releases/releases/download/v{version}/opentelemetry-collector-releases_otelcol-contrib_checksums.txt",
        "tag_prefix": "cmd/otelcorecol/v",
    },
    "node_exporter": {
        "repo": "prometheus/node_exporter",
        "url": "https://github.com/prometheus/node_exporter/releases/download/v{version}/node_exporter-{version}.linux-{arch}.tar.gz",
        "artifact": "node_exporter-{version}.linux-{arch}.tar.gz",
        "checksums": "https://github.com/prometheus/node_exporter/releases/download/v{version}/sha256sums.txt",
    },
    "alertmanager": {
        "repo": "prometheus/alertmanager",
        "url": "https://github.com/prometheus/alertmanager/releases/download/v{version}/alertmanager-{version}.linux-{arch}.tar.gz",
        "artifact": "alertmanager-{version}.linux-{arch}.tar.gz",
        "checksums": "https://github.com/prometheus/alertmanager/releases/download/v{version}/sha256sums.txt",
    },
}

DOCKER_IMAGES = {
    "prometheus": "prom/prometheus:v{version}",
    "loki": "grafana/loki:{version}",
    "tempo": "grafana/tempo:{version}",
    "grafana": "grafana/grafana:{version}",
    "otel_collector": "otel/opentelemetry-collector-contrib:{version}",
    "node_exporter": "prom/node-exporter:v{version}",
    "alertmanager": "prom/alertmanager:v{version}",
}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "signalpost-update-versions"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", errors="replace")


def latest_version(repo: str) -> str:
    data = json.loads(fetch(f"https://api.github.com/repos/{repo}/releases/latest"))
    return data["tag_name"].lstrip("v")


def parse_checksums(text: str) -> dict[str, str]:
    """Parse a `<sha256>  <filename>` listing into {filename: sha256}."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
            out[parts[-1].lstrip("*./")] = parts[0]
    return out


def checksums_for(name: str, spec: dict, version: str) -> dict[str, str]:
    """Return {arch: sha256} for one component at one version."""
    result: dict[str, str] = {}

    if spec.get("checksum_per_arch"):
        for arch in ARCHES:
            raw = fetch(spec["checksums"].format(version=version, arch=arch)).split()
            if not raw or not re.fullmatch(r"[0-9a-f]{64}", raw[0]):
                raise ValueError(f"{name}/{arch}: unexpected checksum payload")
            result[arch] = raw[0]
        return result

    listing = parse_checksums(fetch(spec["checksums"].format(version=version)))
    for arch in ARCHES:
        artifact = spec["artifact"].format(version=version, arch=arch)
        if artifact not in listing:
            raise ValueError(
                f"{name}/{arch}: {artifact} not found in checksum listing "
                f"({len(listing)} entries). Artifact naming may have changed upstream."
            )
        result[arch] = listing[artifact]
    return result


def render(versions: dict[str, str], checksums: dict[str, dict[str, str]]) -> str:
    lines = [
        '"""Pinned component versions and their SHA-256 checksums.',
        "",
        "GENERATED FILE - do not edit by hand.",
        "Regenerate with: python scripts/update_versions.py",
        "",
        "Every version here is paired with the checksum published by that exact",
        "release. install.sh verifies each download against these values and aborts",
        "on a mismatch, so a version bump that skips this script would break the",
        "binary install mode loudly rather than silently weakening it.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "RELEASE_VERSIONS = {",
    ]
    for name in COMPONENTS:
        lines.append(f'    "{name}": "{versions[name]}",')
    lines += ["}", "", "DOCKER_IMAGES = {"]
    for name, image in DOCKER_IMAGES.items():
        lines.append(f'    "{name}": "{image.format(version=versions[name])}",')
    lines += ["}", "", "RELEASE_DOWNLOAD_URLS = {"]
    for name, spec in COMPONENTS.items():
        lines.append(f'    "{name}": "{spec["url"]}",')
    lines += ["}", "", "RELEASE_CHECKSUMS = {"]
    for name in COMPONENTS:
        lines.append(f'    "{name}": {{')
        for arch in ARCHES:
            lines.append(f'        "{arch}": "{checksums[name][arch]}",')
        lines.append("    },")
    lines += ["}", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what would change without writing the file",
    )
    parser.add_argument(
        "--pin",
        action="append",
        default=[],
        metavar="NAME=VERSION",
        help="pin one component instead of taking the latest release",
    )
    args = parser.parse_args()

    pinned = dict(p.split("=", 1) for p in args.pin)
    unknown = set(pinned) - set(COMPONENTS)
    if unknown:
        print(f"unknown component(s): {', '.join(sorted(unknown))}", file=sys.stderr)
        return 2

    versions: dict[str, str] = {}
    checksums: dict[str, dict[str, str]] = {}

    for name, spec in COMPONENTS.items():
        try:
            version = pinned.get(name) or latest_version(spec["repo"])
            print(f"{name:16} {version}", file=sys.stderr)
            versions[name] = version
            checksums[name] = checksums_for(name, spec, version)
        except (urllib.error.URLError, ValueError, KeyError) as exc:
            print(f"{name:16} FAILED: {exc}", file=sys.stderr)
            return 3

    rendered = render(versions, checksums)
    current = OUTPUT_FILE.read_text() if OUTPUT_FILE.exists() else ""

    if rendered == current:
        print("\nversions.py is up to date", file=sys.stderr)
        return 0

    if args.check:
        print("\nversions.py is OUT OF DATE - run without --check", file=sys.stderr)
        return 1

    OUTPUT_FILE.write_text(rendered)
    print(f"\nwrote {OUTPUT_FILE.relative_to(REPO_ROOT)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
