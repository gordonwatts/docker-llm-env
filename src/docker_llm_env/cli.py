import argparse

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
    args = parser.parse_args()

    config = load_config()
    token = config["GITHUB_TOKEN"]

    upstream_owner, repo_name = parse_repo(args.repo)

    print("Authenticating with GitHub...")
    fork_owner = get_authenticated_user(token)
    print(f"Logged in as: {fork_owner}")

    fork_url = ensure_fork(token, upstream_owner, repo_name, fork_owner)
    upstream_url = f"https://github.com/{upstream_owner}/{repo_name}.git"

    build_image_if_needed(force=args.rebuild)

    mode = "shell" if args.shell else "codex"
    run_or_attach(
        owner=upstream_owner,
        repo=repo_name,
        fork_url=fork_url,
        upstream_url=upstream_url,
        github_token=token,
        mode=mode,
    )
