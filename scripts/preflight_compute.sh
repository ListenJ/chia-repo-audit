#!/usr/bin/env bash

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FAILURES=0
WARNINGS=0

pass() {
    printf 'PASS  %s\n' "$1"
}

warn() {
    printf 'WARN  %s\n' "$1"
    WARNINGS=$((WARNINGS + 1))
}

fail() {
    printf 'FAIL  %s\n' "$1"
    FAILURES=$((FAILURES + 1))
}

check_command() {
    local command_name="$1"
    if command -v "$command_name" >/dev/null 2>&1; then
        pass "$command_name: $(command -v "$command_name")"
    else
        warn "$command_name is not installed or not on PATH"
    fi
}

printf 'CHIA compute-window preflight\n'
printf 'Repository: %s\n\n' "$REPO_ROOT"

check_command python3
check_command docker
check_command gcloud
check_command chia
check_command rsync
check_command ssh

if command -v docker >/dev/null 2>&1; then
    if docker info >/dev/null 2>&1; then
        pass "Docker daemon is reachable"
    else
        warn "Docker is installed but the daemon is not reachable"
    fi
fi

if command -v python3 >/dev/null 2>&1; then
    python_version="$(python3 --version 2>&1)"
    pass "$python_version"
fi

if [[ -f "$HOME/.ssh/id_ed25519.pub" ]]; then
    pass "SSH public key exists: $HOME/.ssh/id_ed25519.pub"
else
    warn "No $HOME/.ssh/id_ed25519.pub found; confirm the key planned for GCP"
fi

printf '\nDisk and memory:\n'
df -h "$REPO_ROOT" || true
free -h || true

printf '\nRunning local audit tests...\n'
if (
    cd "$REPO_ROOT" &&
    python3 -m unittest discover -s chia_loop/tests -v
); then
    pass "Local audit tests"
else
    fail "Local audit tests"
fi

printf '\nSummary: %d failure(s), %d warning(s)\n' "$FAILURES" "$WARNINGS"

if [[ "$FAILURES" -gt 0 ]]; then
    exit 1
fi

printf 'Preflight complete. Warnings may represent tools that will only be\n'
printf 'available after the new GCP account arrives.\n'
