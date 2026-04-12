#!/usr/bin/env bash
set -euo pipefail

# ── Codex config (written to volume on first run only) ─────────────────────────
mkdir -p /root/.codex
if [ ! -f /root/.codex/config.toml ]; then
    echo 'cli_auth_credentials_store = "file"' > /root/.codex/config.toml
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

if [ ! -d "${REPO_DIR}/.git" ]; then
    echo "Cloning ${FORK_URL} ..."
    git clone "${FORK_URL}" "${REPO_DIR}"
    if [ "${FORK_URL}" != "${UPSTREAM_URL}" ]; then
        git -C "${REPO_DIR}" remote add upstream "${UPSTREAM_URL}"
        echo "Upstream remote set to: ${UPSTREAM_URL}"
    fi
fi

cd "${REPO_DIR}"

# ── Launch ─────────────────────────────────────────────────────────────────────
if [ "${DOCKER_LLM_MODE:-codex}" = "shell" ]; then
    exec bash
else
    exec codex
fi
