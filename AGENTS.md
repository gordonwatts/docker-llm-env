# Project Guidelines

## Code Style

- Keep changes minimal and consistent with the existing small-module layout under `src/docker_llm_env`.
- Preserve the current standard-library-first import style and straightforward control flow; this repo does not use extra abstraction layers.
- Keep user-facing CLI and `SystemExit` messages explicit because the tool is intended to fail fast on local setup problems.

## Architecture

- The package entrypoint is `docker_llm_env.cli:main`, exposed as the `docker-llm-env` console script.
- `cli.py` orchestrates the flow: load local config, resolve GitHub identity and fork, ensure the Docker image exists, then attach to or launch the per-repository container.
- `github_manager.py` owns GitHub URL parsing and fork lifecycle. Keep owner-selection and fork-detection behavior intact unless the task explicitly changes fork semantics.
- `docker_manager.py` owns Docker-specific behavior, including image hashing from packaged resources, container naming, volume reuse, and attach-vs-run behavior.
- Files under `src/docker_llm_env/resources/` are packaged runtime assets, not loose scripts. If `Dockerfile` or `entrypoint.sh` changes, preserve the resource-hash rebuild behavior in `docker_manager.py`.

## Build And Test

- Install or run locally with `uv run --with . docker-llm-env owner/repo` or `uv tool install git+https://github.com/gordonwatts/docker-llm-env` as documented in [README.md](README.md).
- The project metadata lives in `pyproject.toml`; package sources are under `src/`.
- There is currently no checked-in test suite in this repo. Do not claim test coverage unless you added tests and ran them.
- For functional validation, prefer focused local checks that match the change, for example CLI argument parsing or image/container behavior.

## Conventions

- Runtime configuration is loaded from `~/.docker-llm-env`; avoid moving secrets into repo files or changing the expected config contract casually.
- This tool is designed around persistent Docker state: the named volume stores the home directory and auth state, and each upstream repo gets a stable container name derived from `owner/repo`.
- Re-attaching to an existing container is a core behavior. Changes should not create duplicate containers for the same repo.
- The entrypoint script intentionally performs non-fatal upstream sync for forked repos before launching Codex or a shell. Preserve that best-effort behavior unless the task requires otherwise.
- `~/.agents` is mounted into the container when present on the host. Keep that behavior compatible with repeated runs.
