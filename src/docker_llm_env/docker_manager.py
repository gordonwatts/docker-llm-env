import importlib.resources as pkg_resources
from importlib.resources.abc import Traversable
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

IMAGE_TAG = "docker-llm-env:latest"
VOLUME_NAME = "dlenv-home"
RESOURCES_HASH_LABEL = "dlenv.resources-hash"
DOCKER_SOCKET_PATH = "/var/run/docker.sock"


def _normalized_resource_bytes(resource: Traversable) -> bytes:
    # Ensure text resources are written with LF line endings inside Docker build
    # context even when the local checkout uses CRLF on Windows.
    return resource.read_bytes().replace(b"\r\n", b"\n")


def _resources_hash(resources_root: Traversable) -> str:
    hasher = hashlib.sha256()
    hasher.update(_normalized_resource_bytes(resources_root / "Dockerfile"))
    hasher.update(_normalized_resource_bytes(resources_root / "entrypoint.sh"))
    return hasher.hexdigest()


def _image_resources_hash() -> str | None:
    result = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            IMAGE_TAG,
            "--format",
            f'{{{{ index .Config.Labels "{RESOURCES_HASH_LABEL}" }}}}',
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


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

    resources = pkg_resources.files("docker_llm_env") / "resources"
    expected_hash = _resources_hash(resources)

    if not force:
        result = subprocess.run(
            ["docker", "images", "-q", IMAGE_TAG],
            capture_output=True,
            text=True,
        )
        if result.stdout.strip():
            current_hash = _image_resources_hash()
            if current_hash == expected_hash:
                return  # Image already exists and resources match current package

    print("Building Docker image (this takes a few minutes on first run)...")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        (tmp / "Dockerfile").write_bytes(
            _normalized_resource_bytes(resources / "Dockerfile")
        )
        scripts_dir = tmp / "scripts"
        scripts_dir.mkdir()
        (scripts_dir / "entrypoint.sh").write_bytes(
            _normalized_resource_bytes(resources / "entrypoint.sh")
        )
        result = subprocess.run(
            [
                "docker",
                "build",
                "--label",
                f"{RESOURCES_HASH_LABEL}={expected_hash}",
                "-t",
                IMAGE_TAG,
                str(tmp),
            ],
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


def _container_image_id(name: str) -> str | None:
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.Image}}", name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    image_id = result.stdout.strip()
    return image_id or None


def _current_image_id() -> str | None:
    result = subprocess.run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", IMAGE_TAG],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    image_id = result.stdout.strip()
    return image_id or None


def _container_has_mount(name: str, destination: str) -> bool:
    result = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{range .Mounts}}{{println .Destination}}{{end}}",
            name,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False
    mounts = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    return destination in mounts


def _validate_docker_socket_mount() -> None:
    if sys.platform == "win32":
        return
    if Path(DOCKER_SOCKET_PATH).exists():
        return
    raise SystemExit(
        "Docker daemon socket is not available at /var/run/docker.sock.\n"
        "docker-llm-env now always passes the host Docker daemon through to the container.\n"
        "On Windows, use Docker Desktop with WSL2-backed Linux containers.\n"
        "On Linux, ensure the Docker daemon exposes /var/run/docker.sock."
    )


def run_or_attach(
    owner: str,
    repo: str,
    fork_url: str,
    upstream_url: str,
    github_token: str,
    mode: str,
    agents_dir: Path | None = None,
    clean: bool = False,
    yolo: bool = False,
) -> None:
    name = _container_name(owner, repo)
    status = get_container_status(owner, repo)

    # If container was created from an older image, recreate it so embedded
    # resources (like /scripts/entrypoint.sh) match the current build.
    if status in {"running", "stopped"}:
        container_image = _container_image_id(name)
        latest_image = _current_image_id()
        if container_image and latest_image and container_image != latest_image:
            print("Container uses an outdated image; recreating to apply updates...")
            subprocess.run(
                ["docker", "rm", "-f", name], capture_output=True, check=False
            )
            status = "missing"
        elif not _container_has_mount(name, DOCKER_SOCKET_PATH):
            print(
                "Container is missing the Docker socket mount; recreating to apply updates..."
            )
            subprocess.run(
                ["docker", "rm", "-f", name], capture_output=True, check=False
            )
            status = "missing"

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
    if clean:
        env_args += ["-e", "DOCKER_LLM_CLEAN=1"]
    if yolo:
        env_args += ["-e", "DOCKER_LLM_YOLO=1"]

    # Bind-mount ~/.agents into the container when it exists on the host.
    # Only relevant for `docker run`; `docker exec` inherits the existing mounts.
    agents_mount: list[str] = []
    if agents_dir is not None:
        host_path = str(agents_dir).replace("\\", "/")
        agents_mount = ["-v", f"{host_path}:/root/.agents:ro"]

    if status == "running":
        cmd = (
            ["docker", "exec", "-it"]
            + env_args
            + [name, "/bin/bash", "/scripts/entrypoint.sh"]
        )
    else:
        _validate_docker_socket_mount()
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
                "-v",
                f"{DOCKER_SOCKET_PATH}:{DOCKER_SOCKET_PATH}",
            ]
            + agents_mount
            + env_args
            + [IMAGE_TAG]
        )

    result = subprocess.run(cmd)
    sys.exit(result.returncode)
