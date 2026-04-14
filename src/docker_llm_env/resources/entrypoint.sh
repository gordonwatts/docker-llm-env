#!/usr/bin/env bash
set -euo pipefail

# ── Codex config (written to volume on first run only) ─────────────────────────
mkdir -p /root/.codex
if [ ! -f /root/.codex/config.toml ]; then
    echo 'cli_auth_credentials_store = "file"' > /root/.codex/config.toml
fi

# Append playwright guidance once (idempotent — keyed by marker comment).
# This runs on every start so existing volumes get the update automatically.
# Skip if already injected OR if the user has custom instructions (avoid duplicate TOML keys).
if ! grep -q '#playwright-binaries-note' /root/.codex/config.toml 2>/dev/null && \
    ! grep -q '^instructions' /root/.codex/config.toml 2>/dev/null; then
    cat >> /root/.codex/config.toml << 'TOML'

instructions = """
#playwright-binaries-note
Chromium browser binaries are pre-installed in this container at the path
set by PLAYWRIGHT_BROWSERS_PATH. To write headless-browser tests:
    1. Add playwright to the project: uv add --dev playwright
    2. Do NOT run 'playwright install' — the binaries are already present.
    3. Use sync_playwright or async_playwright from playwright.sync_api / playwright.async_api.
"""
TOML
fi

# ── GitHub CLI authentication ──────────────────────────────────────────────────
echo "${GITHUB_TOKEN}" | gh auth login --with-token --git-protocol https 2>/dev/null || true
gh auth setup-git 2>/dev/null || true

# ── Git identity (set once; persists in /root/.gitconfig on the volume) ────────
if ! git config --global user.name > /dev/null 2>&1; then
    GH_NAME=$(gh api /user --jq '.name // .login' 2>/dev/null || echo "Developer")
    GH_EMAIL=$(gh api /user --jq '.email // (.login + "@users.noreply.github.com")' 2>/dev/null || echo "dev@users.noreply.github.com")
    git config --global user.name "${GH_NAME}"
    git config --global user.email "${GH_EMAIL}"
fi

# ── Clone fork if not already present ─────────────────────────────────────────
REPO_DIR="/root/workspace/${OWNER}/${REPO}"
mkdir -p "/root/workspace/${OWNER}"

if [ "${DOCKER_LLM_CLEAN:-0}" = "1" ] && [ -d "${REPO_DIR}" ]; then
    echo "Cleaning workspace: ${REPO_DIR}"
    rm -rf "${REPO_DIR}"
fi

if [ ! -d "${REPO_DIR}/.git" ]; then
    echo "Cloning ${FORK_URL} ..."
    git clone "${FORK_URL}" "${REPO_DIR}"
    if [ "${FORK_URL}" != "${UPSTREAM_URL}" ]; then
        git -C "${REPO_DIR}" remote add upstream "${UPSTREAM_URL}"
        echo "Upstream remote set to: ${UPSTREAM_URL}"
    fi
fi

cd "${REPO_DIR}"

# ── Sync fork's default branch with upstream ───────────────────────────────────
# Only when an upstream remote exists (i.e. this is a real fork, not a direct clone).
# The entire block is non-fatal — a transient failure here must not prevent launch.
if git remote get-url upstream > /dev/null 2>&1; then
    echo "Fetching upstream..."
    if ! GIT_TERMINAL_PROMPT=0 git fetch upstream --quiet 2>/dev/null; then
        echo "Warning: could not fetch upstream — skipping sync."
    else
        # Discover upstream's default branch directly from the remote.
        # `git ls-remote --symref` is reliable; `remote set-head --auto` is not.
        DEFAULT_BRANCH=$(GIT_TERMINAL_PROMPT=0 git ls-remote --symref upstream HEAD 2>/dev/null \
            | grep '^ref:' \
            | sed 's|^ref: refs/heads/||;s|\tHEAD$||')

        if [ -z "${DEFAULT_BRANCH}" ]; then
            echo "Warning: could not determine upstream default branch — skipping sync."
        else
            LOCAL=$(git rev-parse "${DEFAULT_BRANCH}" 2>/dev/null || true)
            UPSTREAM_REF=$(git rev-parse "upstream/${DEFAULT_BRANCH}" 2>/dev/null || true)

            if [ -z "${LOCAL}" ] || [ -z "${UPSTREAM_REF}" ]; then
                echo "Could not resolve ${DEFAULT_BRANCH} — skipping sync."
            elif [ "${LOCAL}" = "${UPSTREAM_REF}" ]; then
                echo "Fork's ${DEFAULT_BRANCH} is already up to date with upstream."
            elif git merge-base --is-ancestor "${LOCAL}" "${UPSTREAM_REF}"; then
                # Local is strictly behind upstream — safe to fast-forward.
                CURRENT_BRANCH=$(git symbolic-ref --short HEAD 2>/dev/null || true)
                if [ "${CURRENT_BRANCH}" = "${DEFAULT_BRANCH}" ]; then
                    git merge --ff-only "upstream/${DEFAULT_BRANCH}" --quiet
                else
                    git fetch . "upstream/${DEFAULT_BRANCH}:${DEFAULT_BRANCH}" --quiet
                fi
                echo "Synced ${DEFAULT_BRANCH} with upstream (fast-forward)."
            else
                echo "Warning: fork's ${DEFAULT_BRANCH} has diverged from upstream — skipping automatic sync."
            fi
        fi
    fi
fi

# ── Launch ─────────────────────────────────────────────────────────────────────
if [ "${DOCKER_LLM_MODE:-codex}" = "shell" ]; then
    exec bash
else
    CODEX_FLAGS=""
    if [ "${DOCKER_LLM_YOLO:-0}" = "1" ]; then
        CODEX_FLAGS="--dangerously-bypass-approvals-and-sandbox"
        echo "WARNING: Running in YOLO mode with no approvals or sandbox! Use only in trusted environments."
    fi
    # shellcheck disable=SC2086
    exec codex $CODEX_FLAGS
fi
