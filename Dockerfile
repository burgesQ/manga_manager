# Single image used both to run the CLIs and as the Codespaces dev container.
#
#   docker run --rm -it --user "$(id -u):$(id -g)" \
#     -v "$PWD/Manga:/data" -w /data \
#     ghcr.io/burgesq/manga_manager packer --path ./Berserk --serie Berserk --volume 1
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# git + make: needed by the dev container (Codespaces) and `make lint/test`.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git make \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 1) Third-party deps only: this layer is rebuilt only when the lock/manifests change.
#    Every workspace member's pyproject.toml is required for uv to resolve the
#    workspace; `--frozen` fails loudly if a new member is missing here.
COPY pyproject.toml uv.lock .python-version ./
COPY packer/pyproject.toml packer/
COPY editor/pyproject.toml editor/
COPY convertor/pyproject.toml convertor/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-install-workspace

# 2) Workspace packages (needs the sources): cheap, re-run on every code change.
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-packages --no-editable

ENV PATH="/app/.venv/bin:$PATH"

CMD ["bash"]
