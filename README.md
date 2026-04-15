# docker-llm-env

A collection of commands and Docker container specifications for running LLM CLIs in a containerized development environment.

## Overview

This repo provides a reproducible Docker-based setup for working with LLM command-line tools. Rather than installing LLM tooling directly on your host machine, everything runs inside a container, keeping your environment clean and consistent.

Given a GitHub repo, `docker-llm-env` will:

1. Fork the repo to your account (if not already forked)
2. Clone the fork inside a persistent Docker container
3. Launch [OpenAI Codex CLI](https://github.com/openai/codex) pointed at that repo

The container and its home directory (`~/.codex` auth, git config, cloned repos) persist across runs via a Docker volume, so authentication and workspace state are preserved.

The environment also mounts the host Docker daemon socket into the container, so `docker` commands run inside the container against the same daemon as the host.

This is always on. Access to the Docker daemon is effectively host-level control, so only use this tool on machines where that trust boundary is acceptable.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running
- Docker must expose `/var/run/docker.sock` to the environment that launches `docker-llm-env`
- On Windows, use Docker Desktop with WSL2-backed Linux containers
- A GitHub personal access token with `repo` scope

## Configuration

Create `~/.docker-llm-env` with your GitHub token:

```sh
GITHUB_TOKEN=ghp_your_token_here
```

Optional: if your token can fork into an organization (for example `org-name`) but not your personal account, set the fork destination explicitly:

```sh
GITHUB_FORK_OWNER=org-name
```

## Usage

### Run without installing (uvx)

Run directly from the latest commit on GitHub — no local install needed:

```bash
uvx --from git+https://github.com/gordonwatts/docker-llm-env docker-llm-env owner/repo
```

### Install as a persistent tool (uv tool install)

To avoid the startup overhead of `uvx` on every invocation, install it once as a global tool:

```bash
uv tool install git+https://github.com/gordonwatts/docker-llm-env
```

Then run it directly:

```bash
docker-llm-env owner/repo
```

To upgrade to the latest version later:

```bash
uv tool upgrade docker-llm-env
```

### Repo argument formats

```bash
uvx --from git+https://github.com/gordonwatts/docker-llm-env docker-llm-env owner/repo
uvx --from git+https://github.com/gordonwatts/docker-llm-env docker-llm-env github.com/owner/repo
uvx --from git+https://github.com/gordonwatts/docker-llm-env docker-llm-env https://github.com/owner/repo
```

### Options

| Flag | Description |
| ------ | ------------- |
| `--shell` | Drop into bash instead of launching Codex |
| `--rebuild` | Force rebuild of the Docker image |
| `--clean` | Delete the cloned repo inside the container and re-clone from the fork |
| `--no-yolo` | Disable `--dangerously-bypass-approvals-and-sandbox` (it is on by default, since the Linux sandbox may not work inside Docker) |

### Re-attaching

If the container is already running, the same command transparently re-attaches to it via `docker exec` — no duplicate containers are created.

If an existing container was created before the Docker socket mount was added, `docker-llm-env` recreates it automatically so the runtime environment matches the current image and launch contract.

## Getting Started
