# docker-llm-env

A collection of commands and Docker container specifications for running LLM CLIs in a containerized development environment.

## Overview

This repo provides a reproducible Docker-based setup for working with LLM command-line tools. Rather than installing LLM tooling directly on your host machine, everything runs inside a container, keeping your environment clean and consistent.

Given a GitHub repo, `docker-llm-env` will:

1. Fork the repo to your account (if not already forked)
2. Clone the fork inside a persistent Docker container
3. Launch [OpenAI Codex CLI](https://github.com/openai/codex) pointed at that repo

The container and its home directory (`~/.codex` auth, git config, cloned repos) persist across runs via a Docker volume, so authentication and workspace state are preserved.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed and running
- A GitHub personal access token with `repo` scope

## Configuration

Create `~/.docker-llm-env` with your GitHub token:

```
GITHUB_TOKEN=ghp_your_token_here
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

## Getting Started
