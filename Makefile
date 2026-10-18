.PHONY: help build test lint fmt shell dist check-versions update-versions \
        smoke-docker smoke-clean demo

IMAGE := signalpost-dev
COMPOSE := docker compose -f observability/docker-compose.signalpost.yml
RUN_AS := --user $(shell id -u):$(shell id -g)

help:
	@echo "make build             build the signalpost-dev image (test/lint/build environment)"
	@echo "make test              run pytest inside Docker"
	@echo "make lint              run ruff inside Docker"
	@echo "make fmt               run ruff --fix inside Docker"
	@echo "make shell             open a shell inside the dev image, repo mounted"
	@echo "make dist              build sdist/wheel and check them with twine"
	@echo "make check-versions    fail if pinned component versions are behind upstream"
	@echo "make update-versions   regenerate signalpost/versions.py from upstream releases"
	@echo "make smoke-docker      signalpost deploy (docker mode) + real docker compose up + health check"
	@echo "make smoke-clean       tear down and remove the smoke-test stack"

build:
	docker build -t $(IMAGE) --target dev .

test: build
	docker run --rm $(RUN_AS) -v "$(CURDIR)":/src $(IMAGE) pytest -q

lint: build
	docker run --rm $(RUN_AS) -v "$(CURDIR)":/src $(IMAGE) ruff check .

fmt: build
	docker run --rm $(RUN_AS) -v "$(CURDIR)":/src $(IMAGE) ruff check --fix .

shell: build
	docker run --rm -it $(RUN_AS) -v "$(CURDIR)":/src $(IMAGE) bash

dist: build
	docker run --rm $(RUN_AS) -v "$(CURDIR)":/src $(IMAGE) bash -c "rm -rf dist build *.egg-info && python -m build && twine check dist/*"

check-versions:
	python3 scripts/update_versions.py --check

update-versions:
	python3 scripts/update_versions.py

smoke-docker: build
	docker run --rm $(RUN_AS) -v "$(CURDIR)":/src $(IMAGE) rm -rf /src/observability
	mkdir -p /tmp/signalpost-smoke-scan
	docker run --rm $(RUN_AS) \
		-v "$(CURDIR)":/src \
		-v /tmp/signalpost-smoke-scan:/scan \
		-v /var/run/docker.sock:/var/run/docker.sock \
		--group-add $(shell getent group docker | cut -d: -f3 2>/dev/null || echo 0) \
		$(IMAGE) python -m signalpost.cli deploy --path /scan --output /src/observability
	$(COMPOSE) up -d
	./scripts/wait_healthy.sh
	$(COMPOSE) ps

smoke-clean:
	-$(COMPOSE) down -v
	docker run --rm $(RUN_AS) -v "$(CURDIR)":/src $(IMAGE) rm -rf /src/observability

demo: smoke-docker
	@echo "Grafana:      http://localhost:3000  (admin / see observability/secrets/grafana_admin_password.txt)"
	@echo "Prometheus:   http://localhost:9090"
	@echo "Alertmanager: http://localhost:9093"
