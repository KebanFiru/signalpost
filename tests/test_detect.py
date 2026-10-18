from pathlib import Path

from signalpost.constants import ARCH_AMD64, ARCH_ARM64, DEFAULT_PORTS, FALLBACK_PORT
from signalpost.detect import (
    _detect_arch,
    _detect_existing_container,
    _detect_node_framework,
    _detect_python_framework,
    _find_compose_file,
    _guess_port,
    _scan_services,
    detect,
)


def test_detect_arch_returns_known_value(monkeypatch):
    import platform

    monkeypatch.setattr(platform, "machine", lambda: "x86_64")
    assert _detect_arch() == ARCH_AMD64

    monkeypatch.setattr(platform, "machine", lambda: "aarch64")
    assert _detect_arch() == ARCH_ARM64

    monkeypatch.setattr(platform, "machine", lambda: "some_unknown_cpu")
    assert _detect_arch() == ARCH_AMD64


def test_guess_port_matches_uvicorn_pattern(tmp_path: Path):
    (tmp_path / "main.py").write_text('uvicorn.run(app, host="0.0.0.0", port=8123)\n')
    assert _guess_port(tmp_path, "fastapi") == 8123


def test_guess_port_falls_back_to_framework_default(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('no port here')\n")
    assert _guess_port(tmp_path, "fastapi") == DEFAULT_PORTS["fastapi"]


def test_guess_port_falls_back_to_fallback_port_for_unknown_framework(tmp_path: Path):
    assert _guess_port(tmp_path, "unknown-framework") == FALLBACK_PORT


def test_detect_python_framework_identifies_fastapi(tmp_path: Path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("fastapi\nuvicorn\n")
    assert _detect_python_framework(None, requirements) == "fastapi"


def test_detect_python_framework_identifies_django_and_flask(tmp_path: Path):
    django_req = tmp_path / "django_requirements.txt"
    django_req.write_text("Django==5.0\n")
    assert _detect_python_framework(None, django_req) == "django"

    flask_req = tmp_path / "flask_requirements.txt"
    flask_req.write_text("Flask==3.0\n")
    assert _detect_python_framework(None, flask_req) == "flask"


def test_detect_python_framework_defaults_to_python(tmp_path: Path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("requests\n")
    assert _detect_python_framework(None, requirements) == "python"
    assert _detect_python_framework(None, None) == "python"


def test_detect_node_framework_identifies_express_fastify_koa(tmp_path: Path):
    express_pkg = tmp_path / "express.json"
    express_pkg.write_text('{"dependencies": {"express": "^4.0.0"}}')
    assert _detect_node_framework(express_pkg) == "express"

    fastify_pkg = tmp_path / "fastify.json"
    fastify_pkg.write_text('{"dependencies": {"fastify": "^4.0.0"}}')
    assert _detect_node_framework(fastify_pkg) == "fastify"

    koa_pkg = tmp_path / "koa.json"
    koa_pkg.write_text('{"dependencies": {"koa": "^2.0.0"}}')
    assert _detect_node_framework(koa_pkg) == "koa"


def test_detect_node_framework_defaults_to_node(tmp_path: Path):
    pkg = tmp_path / "package.json"
    pkg.write_text('{"dependencies": {}}')
    assert _detect_node_framework(pkg) == "node"


def test_scan_services_finds_python_and_node_services(tmp_path: Path):
    python_service = tmp_path / "api"
    python_service.mkdir()
    (python_service / "pyproject.toml").write_text("[project]\ndependencies = ['fastapi']\n")
    (python_service / "main.py").write_text("app = FastAPI()\n")

    node_service = tmp_path / "web"
    node_service.mkdir()
    (node_service / "package.json").write_text('{"dependencies": {"express": "^4.0.0"}}')

    services = _scan_services(tmp_path)
    names = {s.name for s in services}

    assert names == {"api", "web"}
    api = next(s for s in services if s.name == "api")
    assert api.language == "python"
    assert api.framework == "fastapi"
    web = next(s for s in services if s.name == "web")
    assert web.language == "javascript"
    assert web.framework == "express"


def test_scan_services_skips_skip_dirs(tmp_path: Path):
    skipped = tmp_path / "node_modules" / "some-package"
    skipped.mkdir(parents=True)
    (skipped / "package.json").write_text('{"dependencies": {}}')

    assert _scan_services(tmp_path) == []


def test_scan_services_does_not_recurse_below_max_depth(tmp_path: Path):
    too_deep = tmp_path / "a" / "b" / "c"
    too_deep.mkdir(parents=True)
    (too_deep / "package.json").write_text('{"dependencies": {}}')

    assert _scan_services(tmp_path) == []


def test_scan_services_stops_at_first_service_found_in_a_directory(tmp_path: Path):
    service = tmp_path / "api"
    service.mkdir()
    (service / "pyproject.toml").write_text("[project]\ndependencies = ['fastapi']\n")

    nested = service / "nested"
    nested.mkdir()
    (nested / "package.json").write_text('{"dependencies": {}}')

    services = _scan_services(tmp_path)
    assert len(services) == 1
    assert services[0].name == "api"


def test_find_compose_file_returns_match_or_none(tmp_path: Path):
    assert _find_compose_file(tmp_path) is None

    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n")
    assert _find_compose_file(tmp_path) == compose


def test_detect_existing_container_is_case_insensitive():
    assert _detect_existing_container(["My-Grafana-1"], ("grafana",)) is True
    assert _detect_existing_container(["unrelated"], ("grafana",)) is False


def test_detect_end_to_end_finds_services_under_root(tmp_path: Path):
    service = tmp_path / "api"
    service.mkdir()
    (service / "pyproject.toml").write_text("[project]\ndependencies = ['fastapi']\n")
    (service / "main.py").write_text("app = FastAPI()\n")

    result = detect(tmp_path)

    assert result.root == tmp_path.resolve()
    assert [s.name for s in result.services] == ["api"]
    assert isinstance(result.has_docker, bool)
    assert isinstance(result.has_kubectl, bool)
