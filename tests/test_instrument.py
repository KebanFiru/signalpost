import ast
from pathlib import Path

from signalpost.constants import ALREADY_INSTRUMENTED_MARKER, REQUIRED_PACKAGES
from signalpost.instrument import build_result, instrument

FASTAPI_MAIN = (
    'from fastapi import FastAPI\n\napp = FastAPI()\n\n\n@app.get("/")\ndef root():\n    return {"ok": True}\n'
)

FASTAPI_MAIN_NO_TRAILING_NEWLINE = FASTAPI_MAIN.rstrip("\n")

FASTAPI_FACTORY_MAIN = (
    "from fastapi import FastAPI\n\n\ndef create_app():\n    app = FastAPI()\n    return app\n"
)


def test_build_result_lists_missing_packages(tmp_path: Path):
    (tmp_path / "main.py").write_text(FASTAPI_MAIN)
    (tmp_path / "requirements.txt").write_text("fastapi\nuvicorn\n")

    result = build_result(tmp_path)

    assert result.target_file == tmp_path / "main.py"
    assert result.requirements_additions == REQUIRED_PACKAGES
    assert not result.warnings
    assert not result.already_instrumented


def test_build_result_warns_when_no_requirements_file(tmp_path: Path):
    (tmp_path / "main.py").write_text(FASTAPI_MAIN)

    result = build_result(tmp_path)

    assert result.requirements_file is None
    assert any("requirements.txt" in w for w in result.warnings)


def test_build_result_warns_when_no_entry_file_found(tmp_path: Path):
    result = build_result(tmp_path)

    assert result.target_file == tmp_path / "main.py"
    assert any("No main.py, app.py, server.py found" in w for w in result.warnings)


def test_build_result_detects_already_instrumented(tmp_path: Path):
    (tmp_path / "main.py").write_text(ALREADY_INSTRUMENTED_MARKER + "\n" + FASTAPI_MAIN)

    result = build_result(tmp_path)

    assert result.already_instrumented is True


def test_instrument_apply_writes_source_and_requirements(tmp_path: Path):
    (tmp_path / "main.py").write_text(FASTAPI_MAIN)
    (tmp_path / "requirements.txt").write_text("fastapi\n")

    result = instrument(tmp_path, apply=True)

    assert result.applied is True
    new_source = (tmp_path / "main.py").read_text()
    assert ALREADY_INSTRUMENTED_MARKER in new_source
    assert "FastAPIInstrumentor.instrument_app(app)" in new_source
    ast.parse(new_source)

    new_requirements = (tmp_path / "requirements.txt").read_text()
    for pkg in REQUIRED_PACKAGES:
        assert pkg in new_requirements


def test_instrument_apply_produces_valid_python_when_source_has_no_trailing_newline(tmp_path: Path):
    (tmp_path / "main.py").write_text(FASTAPI_MAIN_NO_TRAILING_NEWLINE)

    result = instrument(tmp_path, apply=True)

    assert result.applied is True
    ast.parse((tmp_path / "main.py").read_text())


def test_instrument_apply_skips_indented_app_assignment_inside_a_factory(tmp_path: Path):
    (tmp_path / "main.py").write_text(FASTAPI_FACTORY_MAIN)

    result = instrument(tmp_path, apply=True)

    assert result.applied is False
    unchanged = (tmp_path / "main.py").read_text()
    assert unchanged == FASTAPI_FACTORY_MAIN
    ast.parse(unchanged)
    assert any("Could not find a `FastAPI(` assignment" in w for w in result.warnings)
    assert not (tmp_path / "requirements.txt").exists()


def test_instrument_apply_skips_source_without_fastapi_assignment(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('no fastapi here')\n")

    result = instrument(tmp_path, apply=True)

    assert result.applied is False
    assert (tmp_path / "main.py").read_text() == "print('no fastapi here')\n"
    assert any("Could not find a `FastAPI(` assignment" in w for w in result.warnings)
    assert not (tmp_path / "requirements.txt").exists()


def test_instrument_apply_is_noop_on_second_run(tmp_path: Path):
    (tmp_path / "main.py").write_text(FASTAPI_MAIN)
    (tmp_path / "requirements.txt").write_text("fastapi\n")

    first = instrument(tmp_path, apply=True)
    assert first.applied is True
    instrumented_source = (tmp_path / "main.py").read_text()

    second = instrument(tmp_path, apply=True)

    assert second.applied is False
    assert (tmp_path / "main.py").read_text() == instrumented_source
    assert any("already has signalpost instrumentation" in w for w in second.warnings)


def test_instrument_apply_warns_when_target_missing(tmp_path: Path):
    result = instrument(tmp_path, apply=True)

    assert result.applied is False
    assert any("does not exist" in w for w in result.warnings)


def test_instrument_apply_creates_requirements_file_when_absent(tmp_path: Path):
    (tmp_path / "main.py").write_text(FASTAPI_MAIN)

    result = instrument(tmp_path, apply=True)

    requirements_path = tmp_path / "requirements.txt"
    assert requirements_path.exists()
    assert result.requirements_file == requirements_path
    assert any("Created" in w for w in result.warnings)
    for pkg in REQUIRED_PACKAGES:
        assert pkg in requirements_path.read_text()
