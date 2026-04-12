import re
import time

import httpx


def parse_repo(repo_arg: str) -> tuple[str, str]:
    """Return (owner, repo) from owner/repo, github.com/owner/repo, or full HTTPS URL."""
    s = repo_arg.strip()
    s = re.sub(r"^https?://", "", s)
    s = re.sub(r"^github\.com/", "", s)
    s = re.sub(r"\.git$", "", s)
    s = s.strip("/")
    parts = s.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise SystemExit(
            f"Cannot parse repo: {repo_arg!r}\n"
            "Expected formats:\n"
            "  owner/repo\n"
            "  github.com/owner/repo\n"
            "  https://github.com/owner/repo"
        )
    return parts[0], parts[1]


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_authenticated_user(token: str) -> str:
    resp = httpx.get("https://api.github.com/user", headers=_headers(token))
    if resp.status_code == 401:
        raise SystemExit(
            "GitHub authentication failed. Check your GITHUB_TOKEN in ~/.docker-llm-env"
        )
    resp.raise_for_status()
    return resp.json()["login"]


def ensure_fork(token: str, upstream_owner: str, repo: str, fork_owner: str) -> str:
    """Ensure a fork of upstream_owner/repo exists under fork_owner. Returns clone URL."""
    hdrs = _headers(token)

    if upstream_owner.lower() == fork_owner.lower():
        print("You own this repo — using it directly.")
        return f"https://github.com/{upstream_owner}/{repo}.git"

    # Check if fork already exists
    resp = httpx.get(f"https://api.github.com/repos/{fork_owner}/{repo}", headers=hdrs)
    if resp.status_code == 200:
        data = resp.json()
        source_name = data.get("source", {}).get("full_name", "")
        if (
            data.get("fork")
            or source_name.lower() == f"{upstream_owner}/{repo}".lower()
        ):
            print(f"Fork already exists: {data['html_url']}")
            return data["clone_url"]

    # Create fork
    print(f"Forking {upstream_owner}/{repo} into your account...")
    resp = httpx.post(
        f"https://api.github.com/repos/{upstream_owner}/{repo}/forks",
        headers=hdrs,
        json={},
    )
    resp.raise_for_status()

    # Poll until fork is ready (GitHub creates it asynchronously)
    print("Waiting for fork to be ready", end="", flush=True)
    for _ in range(30):
        time.sleep(3)
        print(".", end="", flush=True)
        resp = httpx.get(
            f"https://api.github.com/repos/{fork_owner}/{repo}", headers=hdrs
        )
        if resp.status_code == 200 and resp.json().get("full_name"):
            data = resp.json()
            print(f"\nFork ready: {data['html_url']}")
            return data["clone_url"]

    raise SystemExit("\nTimed out waiting for fork to become available.")
