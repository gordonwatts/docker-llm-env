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
    try:
        resp = httpx.get("https://api.github.com/user", headers=_headers(token))
    except httpx.ConnectError as exc:
        raise SystemExit(
            f"Could not reach api.github.com — check your network connection.\n({exc})"
        ) from None
    if resp.status_code == 401:
        raise SystemExit(
            "GitHub authentication failed. Check your GITHUB_TOKEN in ~/.docker-llm-env"
        )
    resp.raise_for_status()
    return resp.json()["login"]


def _list_org_logins(token: str) -> list[str]:
    resp = httpx.get("https://api.github.com/user/orgs", headers=_headers(token))
    if resp.status_code != 200:
        return []
    data = resp.json()
    return [org.get("login", "") for org in data if org.get("login")]


def _is_fork_of(data: dict, upstream_owner: str, repo: str) -> bool:
    source_name = data.get("source", {}).get("full_name", "")
    return (
        bool(data.get("fork"))
        or source_name.lower() == f"{upstream_owner}/{repo}".lower()
    )


def ensure_fork(
    token: str,
    upstream_owner: str,
    repo: str,
    auth_user: str,
    preferred_owner: str | None = None,
) -> str:
    """Ensure a fork exists and return clone URL.

    Owner selection order:
    1) preferred_owner from config (if provided)
    2) authenticated user
    3) organizations visible to the token
    """
    hdrs = _headers(token)

    candidates: list[str] = []

    def add_candidate(owner: str | None) -> None:
        if not owner:
            return
        key = owner.strip()
        if key and key.lower() not in {c.lower() for c in candidates}:
            candidates.append(key)

    add_candidate(preferred_owner)
    add_candidate(auth_user)
    # Only enumerate orgs when no preferred owner is configured — listing orgs
    # can be slow if the token belongs to many organisations.
    if not preferred_owner:
        for org_login in _list_org_logins(token):
            add_candidate(org_login)

    # If the target fork owner IS the upstream owner, no fork is needed.
    # But only short-circuit when there is no preferred_owner pointing elsewhere,
    # otherwise fall through so the fork is created in the preferred org.
    fork_target = (preferred_owner or auth_user).lower()
    if upstream_owner.lower() == fork_target:
        print(f"{upstream_owner} is the fork target — using repo directly.")
        return f"https://github.com/{upstream_owner}/{repo}.git"

    # Check whether a matching fork already exists in candidate owners.
    for owner in candidates:
        resp = httpx.get(f"https://api.github.com/repos/{owner}/{repo}", headers=hdrs)
        if resp.status_code != 200:
            continue
        data = resp.json()
        if _is_fork_of(data, upstream_owner, repo):
            print(f"Fork already exists in {owner}: {data['html_url']}")
            return data["clone_url"]

    # Try creating a fork into each candidate owner until one succeeds.
    errors: list[str] = []
    for owner in candidates:
        payload = {} if owner.lower() == auth_user.lower() else {"organization": owner}
        target = (
            "your account"
            if owner.lower() == auth_user.lower()
            else f"organization {owner}"
        )
        print(f"Forking {upstream_owner}/{repo} into {target}...")
        resp = httpx.post(
            f"https://api.github.com/repos/{upstream_owner}/{repo}/forks",
            headers=hdrs,
            json=payload,
        )

        if resp.status_code in (200, 201, 202):
            print("Waiting for fork to be ready", end="", flush=True)
            for _ in range(30):
                time.sleep(3)
                print(".", end="", flush=True)
                check = httpx.get(
                    f"https://api.github.com/repos/{owner}/{repo}", headers=hdrs
                )
                if check.status_code == 200 and check.json().get("full_name"):
                    data = check.json()
                    print(f"\nFork ready: {data['html_url']}")
                    return data["clone_url"]
            errors.append(f"Timed out waiting for fork in {owner}")
            continue

        try:
            detail = resp.json().get("message", "")
        except Exception:
            detail = resp.text.strip()
        detail = detail or f"HTTP {resp.status_code}"
        errors.append(f"{owner}: {detail}")

    joined = "\n  - ".join(errors) if errors else "No fork targets were available"
    raise SystemExit(
        "Could not create or find a usable fork. Tried these owners:\n"
        f"  - {'\n  - '.join(candidates) if candidates else '(none)'}\n"
        f"Errors:\n  - {joined}"
    )
