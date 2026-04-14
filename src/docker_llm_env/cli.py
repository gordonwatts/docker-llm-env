import argparse
from pathlib import Path

from .config import load_config
from .docker_manager import build_image_if_needed, run_or_attach
from .github_manager import ensure_fork, get_authenticated_user, parse_repo


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="docker-llm-env",
        description="Run OpenAI Codex CLI against a forked GitHub repo inside Docker.",
    )
    parser.add_argument(
        "repo",
        help="GitHub repo: owner/repo, github.com/owner/repo, or full HTTPS URL",
    )
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Drop into bash instead of launching Codex",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Force rebuild of the Docker image",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete the cloned repo inside the container and re-clone from the fork",
    )
    parser.add_argument(
        "--no-yolo",
        dest="yolo",
        action="store_false",
        help="Disable --dangerously-bypass-approvals-and-sandbox (enabled by default)",
    )
    parser.set_defaults(yolo=True)
    args = parser.parse_args()

    config = load_config()
    token = config["GITHUB_TOKEN"]
    preferred_fork_owner = (config.get("GITHUB_FORK_OWNER") or "").strip() or None

    upstream_owner, repo_name = parse_repo(args.repo)

    print("Authenticating with GitHub...")
    auth_user = get_authenticated_user(token)
    print(f"Logged in as: {auth_user}")

    if preferred_fork_owner:
        print(f"Preferred fork owner from config: {preferred_fork_owner}")

    fork_url = ensure_fork(
        token,
        upstream_owner,
        repo_name,
        auth_user,
        preferred_owner=preferred_fork_owner,
    )
    upstream_url = f"https://github.com/{upstream_owner}/{repo_name}.git"

    build_image_if_needed(force=args.rebuild)

    agents_dir = Path.home() / ".agents"
    agents_dir = agents_dir if agents_dir.is_dir() else None
    if agents_dir:
        print(f"Mounting ~/.agents from host: {agents_dir}")

    mode = "shell" if args.shell else "codex"
    run_or_attach(
        owner=upstream_owner,
        repo=repo_name,
        fork_url=fork_url,
        upstream_url=upstream_url,
        github_token=token,
        mode=mode,
        agents_dir=agents_dir,
        clean=args.clean,
        yolo=args.yolo,
    )
