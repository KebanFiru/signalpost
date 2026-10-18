"""ASCII previews of signalpost's Grafana dashboards, rendered with rich.

These are illustrative only — they render against simulated sample data so
a terminal-only user can see what each dashboard looks like before opening
Grafana. Real data always lives in Grafana once the stack is deployed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

BAR_WIDTH = 30
BAR_FILLED = "#"
BAR_EMPTY = "-"
SPARK_CHARS = ".-=+*#%@"


@dataclass
class SampleState:
    cpu_pct: float = 35.0
    mem_pct: float = 50.0
    disk_pct: float = 40.0
    iowait_pct: float = 5.0
    request_rate: float = 40.0
    error_rate_pct: float = 0.5
    p50_ms: float = 45.0
    p95_ms: float = 180.0
    p99_ms: float = 420.0
    history: dict | None = None

    def __post_init__(self) -> None:
        if self.history is None:
            self.history = {
                "cpu": [self.cpu_pct],
                "mem": [self.mem_pct],
                "requests": [self.request_rate],
                "errors": [self.error_rate_pct],
            }

    def step(self) -> None:
        self.cpu_pct = _walk(self.cpu_pct, 0, 100)
        self.mem_pct = _walk(self.mem_pct, 0, 100)
        self.disk_pct = _walk(self.disk_pct, 0, 100, spread=2)
        self.iowait_pct = _walk(self.iowait_pct, 0, 60)
        self.request_rate = _walk(self.request_rate, 0, 200, spread=15)
        self.error_rate_pct = _walk(self.error_rate_pct, 0, 15, spread=1.5)
        self.p50_ms = _walk(self.p50_ms, 5, 300, spread=15)
        self.p95_ms = _walk(self.p95_ms, self.p50_ms, 1200, spread=40)
        self.p99_ms = _walk(self.p99_ms, self.p95_ms, 3000, spread=80)
        history_updates = (
            ("cpu", self.cpu_pct),
            ("mem", self.mem_pct),
            ("requests", self.request_rate),
            ("errors", self.error_rate_pct),
        )
        for key, value in history_updates:
            series = self.history[key]
            series.append(value)
            if len(series) > 20:
                series.pop(0)


def _walk(value: float, low: float, high: float, spread: float = 6.0) -> float:
    value += random.uniform(-spread, spread)
    return max(low, min(high, value))


def _sparkline(values: list[float], vmax: float | None = None) -> str:
    if not values:
        return ""
    vmax = vmax or max(values) or 1.0
    scale = (len(SPARK_CHARS) - 1) / vmax
    return "".join(SPARK_CHARS[min(len(SPARK_CHARS) - 1, max(0, int(v * scale)))] for v in values)


def _bar(pct: float, width: int = BAR_WIDTH) -> Text:
    filled = int(width * max(0.0, min(100.0, pct)) / 100)
    color = "green" if pct < 70 else "yellow" if pct < 90 else "red"
    text = Text()
    text.append(BAR_FILLED * filled, style=color)
    text.append(BAR_EMPTY * (width - filled), style="grey37")
    text.append(f" {pct:5.1f}%")
    return text


def render_host_basics(state: SampleState) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="left", width=14)
    table.add_column()
    table.add_row("CPU", _bar(state.cpu_pct))
    table.add_row("Memory", _bar(state.mem_pct))
    table.add_row("Disk", _bar(state.disk_pct))
    table.add_row("I/O wait", _bar(state.iowait_pct))
    table.add_row("CPU trend", Text(_sparkline(state.history["cpu"], vmax=100), style="cyan"))
    table.add_row("Mem trend", Text(_sparkline(state.history["mem"], vmax=100), style="magenta"))
    return Panel(table, title="signalpost / Host Basics", border_style="cyan")


def render_stack_selfhealth(state: SampleState, up: dict[str, bool]) -> Panel:
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left", width=16)
    table.add_column()
    for name, is_up in up.items():
        label = Text("[UP]" if is_up else "[DOWN]", style="bold green" if is_up else "bold red")
        table.add_row(name, label)
    return Panel(table, title="signalpost / Stack Self-Health", border_style="cyan")


def render_http_red(state: SampleState, job_names: list[str]) -> Panel:
    jobs = ", ".join(job_names) if job_names else "(no web services detected yet)"
    table = Table.grid(padding=(0, 1))
    table.add_column(justify="left", width=16)
    table.add_column()
    request_trend = f"{state.request_rate:6.1f} req/s  " + _sparkline(state.history["requests"], vmax=200)
    table.add_row("Request rate", Text(request_trend, style="cyan"))
    table.add_row("Error rate", _bar(state.error_rate_pct, width=BAR_WIDTH))
    table.add_row("p50 latency", Text(f"{state.p50_ms:6.0f} ms"))
    table.add_row("p95 latency", Text(f"{state.p95_ms:6.0f} ms", style="yellow"))
    table.add_row("p99 latency", Text(f"{state.p99_ms:6.0f} ms", style="red"))

    logs = Text()
    for _ in range(3):
        trace_id = "".join(random.choice("abcdef0123456789") for _ in range(16))
        logs.append("INFO ", style="green")
        logs.append(f"[trace_id={trace_id}] ", style="cyan")
        logs.append("GET /api/v1/resource 200 12ms\n")

    group = Group(
        Panel(table, title=f"jobs: {jobs}", border_style="cyan"),
        Panel(logs, title="Logs (click a trace_id in Grafana to jump to its trace)", border_style="grey50"),
    )
    return Panel(group, title="signalpost / HTTP RED", border_style="cyan")


def render_dashboard(name: str, state: SampleState, job_names: list[str] | None = None) -> Panel:
    if name == "host-basics":
        return render_host_basics(state)
    if name == "stack-selfhealth":
        up = {"prometheus": True, "loki": True, "tempo": True, "grafana": True, "otel-collector": True}
        return render_stack_selfhealth(state, up)
    if name == "http-red":
        return render_http_red(state, job_names or [])
    raise ValueError(f"unknown dashboard: {name}")
