import importlib.resources as pkg_resources
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IMAGE_TAG = "docker-llm-env:latest"
VOLUME_NAME = "dlenv-home"


def _container_name(owner: str, repo: str) -> str:
    raw = f"dlenv-{owner}-{repo}".lower()
    return re.sub(r"[^a-z0-9-]", "-", raw)


def _check_docker() -> None:
    if not shutil.which("docker"):
        raise SystemExit(
            "Docker CLI not found.\n"
            "Install Docker from: https://docs.docker.com/get-docker/"
        )
    result = subprocess.run(["docker", "info"], capture_output=True)
    if result.returncode != 0:
        raise SystemExit(
            "Docker daemon is not running.\n"
            "Start Docker Desktop (or run: sudo systemctl start docker)"
        )


def build_image_if_needed(force: bool = False) -> None:
    _check_docker()

    if not force:
        result = subprocess.run(
            ["docker", "images", "-q", IMAGE_TAG],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            return  # Image already exists

    print("Building Docker image (this takes a few minutes on first run)...")

    resources = pkg_resources.files("docker_llm_env") / "resources"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "Dockerfile").write_bytes((resources / "Dockerfile").read_bytes())
        scripts_dir = tmp / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "entrypoint.sh").write_bytes(
            (resources / "entrypoint.sh").read_bytes()
        )
        result = subprocess.run(
            ["docker", "build", "-t", IMAGE_TAG, str(tmp)],
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit("Docker image build failed.")

    print("Image built successfully.")


def get_container_status(owner: str, repo: str) -> str:
    name = _container_name(owner, repo)
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Status}}", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return "missing"
    status = result.stdout.strip()
    return "running" if status == "running" else "stopped"


def run_or_attach(
    owner: str,
    repo: str,
    fork_url: str,
    upstream_url: str,
    github_token: str,
    mode: str,
) -> None:
    name = _container_name(owner, repo)
    status = get_container_status(owner, repo)

    env_args = [
        "-e",
        f"GITHUB_TOKEN={github_token}",
        "-e",
        f"FORK_URL={fork_url}",
        "-e",
        f"UPSTREAM_URL={upstream_url}",
        "-e",
        f"OWNER={owner}",
        "-e",
        f"REPO={repo}",
        "-e",
        f"DOCKER_LLM_MODE={mode}",
    ]

    if status == "running":
        cmd = (
            ["docker", "exec", "-it"]
            + env_args
            + [name, "/bin/bash", "/scripts/entrypoint.sh"]
        )
    else:
        if status == "stopped":
            # Remove stale stopped container; volume preserves all state
            subprocess.run(["docker", "rm", name], capture_output=True, check=False)
        cmd = (
            [
                "docker",
                "run",
                "--rm",
                "-it",
                "--name",
                name,
                "-v",
                f"{VOLUME_NAME}:/root",
            ]
            + env_args
            + [IMAGE_TAG]
        )

    result = subprocess.run(cmd)
    sys.exit(result.returncode)
