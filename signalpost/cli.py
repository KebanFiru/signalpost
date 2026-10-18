"""signalpost's command-line interface, built on click and rendered with rich."""

from __future__ import annotations

import time
from pathlib import Path

import click
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from signalpost.constants import (
    ALERT_PACKAGE_DESCRIPTIONS,
    DASHBOARD_DESCRIPTIONS,
    DASHBOARD_NAMES,
    INSTALL_MODE_DOCKER,
)
from signalpost.dashboard_preview import SampleState, render_dashboard
from signalpost.deploy import deploy as run_deploy
from signalpost.detect import detect
from signalpost.instrument import instrument as run_instrument
from signalpost.models import DetectionResult, Plan
from signalpost.planner import plan as build_plan

console = Console()


def _run_detect_and_plan(root: Path, notify_url: str | None = None) -> tuple[DetectionResult, Plan]:
    detection = detect(root)
    plan_result = build_plan(detection, notify_url=notify_url)
    return detection, plan_result


_NOTIFY_OPTION = click.option(
    "--notify",
    "notify_url",
    default=None,
    metavar="URL",
    help="Where fired alerts should be delivered: a Slack incoming-webhook URL, a Discord "
    "webhook URL, or any HTTPS webhook. Without this, Alertmanager still runs but nothing "
    "is notified.",
)


def _print_detection_summary(detection: DetectionResult) -> None:
    table = Table(title="Detected environment", show_header=True, header_style="bold cyan")
    table.add_column("Fact")
    table.add_column("Value")
    table.add_row("Root", str(detection.root))
    table.add_row("Docker available", "yes" if detection.has_docker else "no")
    table.add_row("kubectl available", "yes" if detection.has_kubectl else "no")
    table.add_row("Existing compose file", str(detection.existing_compose_file or "none"))
    table.add_row("Existing Prometheus", "yes" if detection.existing_prometheus else "no")
    table.add_row("Existing Grafana", "yes" if detection.existing_grafana else "no")
    table.add_row("CPU count", str(detection.cpu_count))
    table.add_row("Total RAM", f"{detection.total_ram_gb:.1f} GB")
    table.add_row("Disk free", f"{detection.disk_free_gb:.1f} GB")
    services_str = ", ".join(f"{s.name} ({s.framework}:{s.port_guess})" for s in detection.services) or "none"
    table.add_row("Services", services_str)
    console.print(table)


def _print_plan(plan_result: Plan) -> None:
    decisions_table = Table(title="Decisions", show_header=True, header_style="bold green")
    decisions_table.add_column("#", width=3)
    decisions_table.add_column("Rationale")
    for i, decision in enumerate(plan_result.decisions, start=1):
        decisions_table.add_row(str(i), decision)
    console.print(decisions_table)

    summary_table = Table(title="Plan summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Setting")
    summary_table.add_column("Value")
    summary_table.add_row("Log retention", f"{plan_result.log_retention_days}d")
    summary_table.add_row("Trace retention", f"{plan_result.trace_retention_days}d")
    summary_table.add_row("Metric retention", f"{plan_result.metric_retention_days}d")
    summary_table.add_row("Trace sampling", f"{plan_result.sampling_pct}%")
    summary_table.add_row("Loki per-stream limit", f"{plan_result.loki_ingest_mbps}MB/s")
    for component, mb in plan_result.memory_limits.items():
        summary_table.add_row(f"Memory: {component}", f"{mb}MB")
    summary_table.add_row("Prometheus port", str(plan_result.prometheus_port))
    summary_table.add_row("Install mode", plan_result.install_mode)
    summary_table.add_row("Alert packages", ", ".join(plan_result.alert_packages))
    console.print(summary_table)

    if plan_result.scrape_targets:
        targets_table = Table(title="Scrape targets", show_header=True, header_style="bold blue")
        targets_table.add_column("Job")
        targets_table.add_column("Target")
        for t in plan_result.scrape_targets:
            targets_table.add_row(t.job_name, t.target)
        console.print(targets_table)

    if plan_result.warnings:
        for warning in plan_result.warnings:
            console.print(Panel(warning, title="Warning", border_style="yellow"))


@click.group()
@click.version_option(package_name="signalpost")
def main() -> None:
    """signalpost: an opinionated Grafana/Loki/Tempo/Prometheus/OTel installer."""


@main.command()
@click.option(
    "--path",
    "root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Directory to scan (defaults to current directory).",
)
@_NOTIFY_OPTION
def init(root: Path, notify_url: str | None) -> None:
    """Detect the environment and show the plan with its rationale."""
    detection, plan_result = _run_detect_and_plan(root, notify_url)
    _print_detection_summary(detection)
    _print_plan(plan_result)
    console.print(
        Panel(
            "Run [bold]signalpost deploy[/bold] to render the stack, or [bold]signalpost deploy --dry-run[/bold] "
            "to preview the files first.",
            title="Next step",
            border_style="cyan",
        )
    )


@main.command()
@click.option(
    "--path",
    "root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Directory to scan (defaults to current directory).",
)
@_NOTIFY_OPTION
def plan(root: Path, notify_url: str | None) -> None:
    """Show the plan (decisions + settings) without writing anything."""
    _, plan_result = _run_detect_and_plan(root, notify_url)
    _print_plan(plan_result)


@main.command()
@click.option(
    "--path",
    "root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Directory to scan (defaults to current directory).",
)
@click.option(
    "--output",
    "output_dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
    help="Where to render the stack (defaults to <path>/observability).",
)
@click.option("--dry-run", is_flag=True, help="Show what would be written without touching disk.")
@_NOTIFY_OPTION
def deploy(root: Path, output_dir: Path | None, dry_run: bool, notify_url: str | None) -> None:
    """Render the stack and write it to disk."""
    detection, plan_result = _run_detect_and_plan(root, notify_url)
    _print_plan(plan_result)

    result = run_deploy(plan_result, detection, output_dir=output_dir, dry_run=dry_run)

    verb = "Would write" if dry_run else "Wrote"
    files_table = Table(title=f"{verb} files", show_header=True, header_style="bold green")
    files_table.add_column("Path")
    for f in result.written:
        files_table.add_row(str(f))
    console.print(files_table)

    if result.backed_up:
        backup_table = Table(title="Backed up existing files", show_header=True, header_style="bold yellow")
        backup_table.add_column("Path")
        for f in result.backed_up:
            backup_table.add_row(str(f))
        console.print(backup_table)

    for warning in result.warnings:
        console.print(Panel(warning, title="Warning", border_style="yellow"))

    if dry_run:
        console.print(Panel("Dry run — nothing was written.", border_style="cyan"))
        return

    if plan_result.install_mode == INSTALL_MODE_DOCKER:
        next_step = f"cd {result.output_dir} && docker compose -f docker-compose.signalpost.yml up -d"
    else:
        next_step = f"cd {result.output_dir} && sudo ./install.sh"

    console.print(
        Panel(
            f"Grafana admin password: [bold]{result.grafana_password_file}[/bold]\n\n"
            f"Next step ({plan_result.install_mode} mode):\n[bold]{next_step}[/bold]",
            title="Deploy complete",
            border_style="green",
        )
    )


@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
@click.option("--apply", "apply_", is_flag=True, help="Apply the changes instead of just showing them.")
def instrument(path: Path, apply_: bool) -> None:
    """Show (or apply, with --apply) OTel instrumentation for a FastAPI service."""
    result = run_instrument(path, apply=apply_)

    console.print(Panel(f"Service name: [bold]{result.service_name}[/bold]\nTarget file: {result.target_file}"))

    if result.requirements_additions:
        req_table = Table(title="Packages to add", show_header=True, header_style="bold magenta")
        req_table.add_column("Package")
        for pkg in result.requirements_additions:
            req_table.add_row(pkg)
        console.print(req_table)
    else:
        console.print("[green]All required packages already present.[/green]")

    console.print(Syntax(result.import_snippet + result.instrument_call_snippet, "python", theme="ansi_dark"))

    for warning in result.warnings:
        console.print(Panel(warning, title="Warning", border_style="yellow"))

    if apply_:
        if result.applied:
            console.print(Panel(f"Applied instrumentation to {result.target_file}.", border_style="green"))
        else:
            console.print(Panel("Not applied — see warnings above.", border_style="red"))
    else:
        console.print(
            Panel(
                "This was a preview only. Re-run with [bold]--apply[/bold] to write these changes.",
                border_style="cyan",
            )
        )


@main.command()
@click.option(
    "--path",
    "root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Directory to scan (defaults to current directory).",
)
def alerts(root: Path) -> None:
    """List the alert packages the plan would enable, and why."""
    _, plan_result = _run_detect_and_plan(root)
    table = Table(title="Active alert packages", show_header=True, header_style="bold green")
    table.add_column("Package")
    table.add_column("Covers")
    for package in plan_result.alert_packages:
        table.add_row(package, ALERT_PACKAGE_DESCRIPTIONS.get(package, ""))
    console.print(table)


@main.command()
@click.option(
    "--preview",
    "preview_name",
    type=click.Choice(DASHBOARD_NAMES),
    default=None,
    help="Show an ASCII preview of one dashboard using simulated sample data.",
)
@click.option("--live", is_flag=True, help="Animate the preview with simulated data until Ctrl+C.")
@click.option(
    "--path",
    "root",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    default=Path("."),
    help="Directory to scan (used to scope the http-red preview to detected web services).",
)
def dashboards(preview_name: str | None, live: bool, root: Path) -> None:
    """List signalpost's provisioned Grafana dashboards, or preview one as ASCII."""
    if preview_name is None:
        table = Table(title="Provisioned Grafana dashboards", show_header=True, header_style="bold green")
        table.add_column("Dashboard")
        table.add_column("Shows")
        for name in DASHBOARD_NAMES:
            table.add_row(name, DASHBOARD_DESCRIPTIONS.get(name, ""))
        console.print(table)
        console.print(
            Panel(
                "Preview one in the terminal: [bold]signalpost dashboards --preview host-basics[/bold] "
                "(add [bold]--live[/bold] to animate it with simulated data).",
                border_style="cyan",
            )
        )
        return

    job_names: list[str] = []
    if preview_name == "http-red":
        _, plan_result = _run_detect_and_plan(root)
        job_names = [
            t.job_name
            for t in plan_result.scrape_targets
            if t.service.framework in ("fastapi", "flask", "django")
        ]

    state = SampleState()
    if not live:
        console.print(render_dashboard(preview_name, state, job_names))
        return

    try:
        with Live(render_dashboard(preview_name, state, job_names), console=console, refresh_per_second=2) as live_view:
            while True:
                time.sleep(0.5)
                state.step()
                live_view.update(render_dashboard(preview_name, state, job_names))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
