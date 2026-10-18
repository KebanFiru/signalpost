"""Environment detection: gather facts about the host and its services.

This module never makes decisions — it only observes. Decision-making
lives in :mod:`signalpost.planner`. Every probe is best-effort: a failure
to detect one thing must never prevent detection of anything else.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

from signalpost.constants import (
    ARCH_ALIASES,
    ARCH_AMD64,
    COMPOSE_FILE_CANDIDATES,
    DEFAULT_PORTS,
    FALLBACK_PORT,
    GRAFANA_CONTAINER_KEYWORDS,
    MAX_DEPTH,
    PORT_GUESS_FILE_CANDIDATES,
    PORT_PATTERNS,
    PROMETHEUS_CONTAINER_KEYWORDS,
    SKIP_DIRS,
)
from signalpost.models import DetectionResult, Service


def _detect_arch() -> str:
    try:
        machine = platform.machine().lower()
        return ARCH_ALIASES.get(machine, ARCH_AMD64)
    except Exception:
        return ARCH_AMD64


def _which(cmd: str) -> bool:
    try:
        return shutil.which(cmd) is not None
    except Exception:
        return False


def _find_compose_file(root: Path) -> Path | None:
    for name in COMPOSE_FILE_CANDIDATES:
        p = root / name
        try:
            if p.exists():
                return p
        except Exception:
            continue
    return None


def _running_container_names() -> list[str]:
    if not _which("docker"):
        return []
    try:
        out = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if out.returncode != 0:
            return []
        return [line.strip() for line in out.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def _detect_existing_container(names: list[str], keywords: tuple[str, ...]) -> bool:
    try:
        lowered = [n.lower() for n in names]
        return any(any(kw in n for kw in keywords) for n in lowered)
    except Exception:
        return False


def _cpu_count() -> int:
    try:
        import os

        n = os.cpu_count()
        return n if n else 1
    except Exception:
        return 1


def _total_ram_gb() -> float:
    try:
        import psutil

        return round(psutil.virtual_memory().total / (1024**3), 2)
    except Exception:
        pass
    try:
        import ctypes
        import sys

        if sys.platform.startswith("win"):
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / (1024**3), 2)
        else:
            import os

            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            return round(pages * page_size / (1024**3), 2)
    except Exception:
        return 0.0


def _disk_free_gb(root: Path) -> float:
    try:
        usage = shutil.disk_usage(root)
        return round(usage.free / (1024**3), 2)
    except Exception:
        return 0.0


def _guess_port(service_dir: Path, framework: str) -> int:
    for fname in PORT_GUESS_FILE_CANDIDATES:
        fpath = service_dir / fname
        try:
            if not fpath.exists() or not fpath.is_file():
                continue
            text = fpath.read_text(encoding="utf-8", errors="ignore")
            for pattern in PORT_PATTERNS:
                match = pattern.search(text)
                if match:
                    port = int(match.group(1))
                    if 1 <= port <= 65535:
                        return port
        except Exception:
            continue
    return DEFAULT_PORTS.get(framework, FALLBACK_PORT)


def _detect_python_framework(pyproject: Path | None, requirements: Path | None) -> str:
    text = ""
    for f in (pyproject, requirements):
        try:
            if f and f.exists():
                text += f.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
    if "fastapi" in text:
        return "fastapi"
    if "django" in text:
        return "django"
    if "flask" in text:
        return "flask"
    return "python"


def _detect_node_framework(package_json: Path) -> str:
    try:
        text = package_json.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return "node"
    if "fastify" in text:
        return "fastify"
    if "koa" in text:
        return "koa"
    if "express" in text:
        return "express"
    return "node"


def _scan_services(root: Path) -> list[Service]:
    services: list[Service] = []

    def _walk(directory: Path, depth: int) -> None:
        if depth > MAX_DEPTH:
            return
        try:
            entries = list(directory.iterdir())
        except Exception:
            return

        found_here = False
        try:
            requirements = directory / "requirements.txt"
            pyproject = directory / "pyproject.toml"
            package_json = directory / "package.json"

            if requirements.exists() or pyproject.exists():
                framework = _detect_python_framework(
                    pyproject if pyproject.exists() else None,
                    requirements if requirements.exists() else None,
                )
                port = _guess_port(directory, framework)
                services.append(
                    Service(
                        name=directory.name,
                        language="python",
                        framework=framework,
                        path=directory,
                        port_guess=port,
                    )
                )
                found_here = True

            if not found_here and package_json.exists():
                framework = _detect_node_framework(package_json)
                port = _guess_port(directory, framework)
                services.append(
                    Service(
                        name=directory.name,
                        language="javascript",
                        framework=framework,
                        path=directory,
                        port_guess=port,
                    )
                )
                found_here = True
        except Exception:
            pass

        if found_here:
            return

        for entry in entries:
            try:
                if entry.is_dir() and entry.name not in SKIP_DIRS and not entry.name.startswith("."):
                    _walk(entry, depth + 1)
            except Exception:
                continue

    _walk(root, 0)
    return services


def detect(root: Path | None = None) -> DetectionResult:
    """Gather all environment facts under ``root`` (defaults to cwd)."""
    root = (root or Path.cwd()).resolve()

    container_names = _running_container_names()

    return DetectionResult(
        root=root,
        has_docker=_which("docker"),
        has_kubectl=_which("kubectl"),
        existing_compose_file=_find_compose_file(root),
        existing_prometheus=_detect_existing_container(container_names, PROMETHEUS_CONTAINER_KEYWORDS),
        existing_grafana=_detect_existing_container(container_names, GRAFANA_CONTAINER_KEYWORDS),
        services=_scan_services(root),
        cpu_count=_cpu_count(),
        total_ram_gb=_total_ram_gb(),
        disk_free_gb=_disk_free_gb(root),
        arch=_detect_arch(),
    )
