"""Generate (and optionally apply) OpenTelemetry instrumentation for a FastAPI service.

By default this module only *shows* what it would change — a requirements
diff and a code snippet. Nothing touches the user's files unless they pass
``apply=True`` (wired to the CLI's ``--apply`` flag), and even then only
for changes this module is confident are safe (see :func:`instrument`).
"""

from __future__ import annotations

from pathlib import Path

from signalpost.constants import (
    ALREADY_INSTRUMENTED_MARKER,
    APP_CREATION_PATTERN,
    ENTRY_FILE_CANDIDATES,
    IMPORT_SNIPPET_TEMPLATE,
    INSTRUMENT_CALL_TEMPLATE,
    OTLP_ENDPOINT,
    REQUIRED_PACKAGES,
)
from signalpost.models import InstrumentResult


def _find_entry_file(path: Path) -> Path | None:
    if path.is_file():
        return path
    for candidate in ENTRY_FILE_CANDIDATES:
        candidate_path = path / candidate
        if candidate_path.exists():
            return candidate_path
    return None


def _find_requirements_file(entry_file: Path) -> Path | None:
    req = entry_file.parent / "requirements.txt"
    return req if req.exists() else None


def _missing_packages(requirements_file: Path | None) -> list[str]:
    if requirements_file is None:
        return list(REQUIRED_PACKAGES)
    try:
        text = requirements_file.read_text(encoding="utf-8", errors="ignore").lower()
    except Exception:
        return list(REQUIRED_PACKAGES)
    return [pkg for pkg in REQUIRED_PACKAGES if pkg not in text]


def build_result(path: Path) -> InstrumentResult:
    """Compute (without applying) the snippet/diff signalpost would produce for ``path``."""
    entry_file = _find_entry_file(path)
    warnings: list[str] = []
    if entry_file is None:
        entry_file = path if path.is_file() else path / "main.py"
        warnings.append(
            f"No {', '.join(ENTRY_FILE_CANDIDATES)} found under {path} — "
            "showing a snippet you'll need to place manually."
        )

    service_name = entry_file.parent.name if entry_file.parent.name else entry_file.stem
    requirements_file = _find_requirements_file(entry_file)
    if requirements_file is None:
        warnings.append(f"No requirements.txt found next to {entry_file} — list packages manually.")

    already_instrumented = False
    if entry_file.exists():
        try:
            existing = entry_file.read_text(encoding="utf-8", errors="ignore")
            already_instrumented = ALREADY_INSTRUMENTED_MARKER in existing
        except Exception:
            pass

    import_snippet = IMPORT_SNIPPET_TEMPLATE.format(
        marker=ALREADY_INSTRUMENTED_MARKER,
        service_name=service_name,
        otlp_endpoint=OTLP_ENDPOINT,
    )
    instrument_call_snippet = INSTRUMENT_CALL_TEMPLATE.format(
        app_var="app", marker=ALREADY_INSTRUMENTED_MARKER
    )

    return InstrumentResult(
        target_file=entry_file,
        requirements_file=requirements_file,
        service_name=service_name,
        requirements_additions=_missing_packages(requirements_file),
        import_snippet=import_snippet,
        instrument_call_snippet=instrument_call_snippet,
        already_instrumented=already_instrumented,
        warnings=warnings,
    )


def _apply_to_requirements(result: InstrumentResult) -> None:
    if not result.requirements_additions:
        return
    if result.requirements_file is None:
        result.requirements_file = result.target_file.parent / "requirements.txt"
        result.warnings.append(f"Created {result.requirements_file} (none existed).")
    with result.requirements_file.open("a", encoding="utf-8") as f:
        if result.requirements_file.stat().st_size > 0:
            f.write("\n")
        f.write("\n".join(result.requirements_additions) + "\n")


def _apply_to_source(result: InstrumentResult) -> None:
    text = result.target_file.read_text(encoding="utf-8")
    match = APP_CREATION_PATTERN.search(text)
    if match is None:
        result.warnings.append(
            f"Could not find a `FastAPI(` assignment in {result.target_file} — "
            "code snippet was not applied. Paste it in manually."
        )
        return

    app_var = match.group(1)
    insertion_point = match.end()
    line_end = text.find("\n", insertion_point)
    if line_end == -1:
        text += "\n"
        line_end = len(text)
    else:
        line_end += 1

    call_snippet = INSTRUMENT_CALL_TEMPLATE.format(app_var=app_var, marker=ALREADY_INSTRUMENTED_MARKER)

    new_text = text[:line_end] + call_snippet + text[line_end:]
    new_text = result.import_snippet + "\n" + new_text
    result.target_file.write_text(new_text, encoding="utf-8")


def instrument(path: Path, apply: bool = False) -> InstrumentResult:
    """Build the instrumentation plan for ``path``, applying it if ``apply`` is True.

    ``path`` may be a service directory or a direct path to its entry file.
    Application is skipped (with a warning, not an exception) whenever
    signalpost isn't confident it can make a safe edit — e.g. no recognizable
    ``app = FastAPI(...)`` line, or the file is already instrumented.
    """
    result = build_result(path)

    if not apply:
        return result

    if result.already_instrumented:
        result.warnings.append(f"{result.target_file} already has signalpost instrumentation — skipped.")
        return result

    if not result.target_file.exists():
        result.warnings.append(f"{result.target_file} does not exist — cannot apply.")
        return result

    _apply_to_source(result)
    result.applied = ALREADY_INSTRUMENTED_MARKER in result.target_file.read_text(
        encoding="utf-8", errors="ignore"
    )
    if result.applied:
        _apply_to_requirements(result)
    return result
