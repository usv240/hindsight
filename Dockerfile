# Hindsight evidence console - public read-only demo.
#
# Serves the runs that were already recorded, with both mutating routes
# refused before they do any work (see src/hindsight/web/demo_mode.py).
# Nothing is written at runtime, so there is no volume and no database:
# the evidence is baked into the image and the container is disposable.
#
# Build and run locally exactly as the host will:
#   docker build -t hindsight .
#   docker run --rm -p 8100:8100 -e HINDSIGHT_PUBLIC_DEMO=1 hindsight

FROM python:3.12-slim AS build

COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dependencies resolve from the lockfile in their own layer, so editing the
# application does not re-resolve 161 MB of scipy and scikit-learn.
# LICENSE too: hatchling reads `license = {file = "LICENSE"}` while building
# the project's own wheel, and fails the whole sync without it.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-install-project --no-dev

COPY src ./src
RUN uv sync --locked --no-dev


FROM python:3.12-slim

# The demo never writes, so it never needs to be root.
RUN useradd --create-home --uid 10001 hindsight
WORKDIR /app

COPY --from=build --chown=hindsight:hindsight /app/.venv /app/.venv
COPY --chown=hindsight:hindsight src ./src

# The evidence the console serves. Recorded runs, the DataHub fixture they
# replay, the audit configs, and the sample artifacts the evidence page reads
# off disk - without these the site renders empty.
COPY --chown=hindsight:hindsight evidence ./evidence
COPY --chown=hindsight:hindsight fixtures ./fixtures
COPY --chown=hindsight:hindsight audits ./audits
COPY --chown=hindsight:hindsight scenarios ./scenarios
COPY --chown=hindsight:hindsight examples ./examples
COPY --chown=hindsight:hindsight pyproject.toml README.md LICENSE ./

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    HINDSIGHT_PUBLIC_DEMO=1

USER hindsight
EXPOSE 8100

# Hosts inject $PORT and expect the process to honour it. Falling back to 8100
# keeps `docker run -p 8100:8100` working unchanged.
# --factory rather than a module-level app: create_app() resolves the project
# root from cwd, and an import-time singleton would fix that at import.
CMD ["sh", "-c", "exec uvicorn hindsight.web.app:create_app --factory --host 0.0.0.0 --port ${PORT:-8100}"]
