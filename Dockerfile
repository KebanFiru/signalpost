FROM python:3.12-slim AS dev

COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /src

COPY pyproject.toml README.md ./
COPY signalpost/__init__.py signalpost/__init__.py
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e ".[dev]" ruff build twine

COPY . .
RUN pip install --no-cache-dir -e ".[dev]"

CMD ["pytest", "-q"]
