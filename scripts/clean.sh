#!/usr/bin/env bash
set -euo pipefail

# Repository-local cleanup (generated artifacts only)
# Safe to run anytime.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

rm -rf \
  .pytest_cache \
  .mypy_cache \
  htmlcov \
  __pycache__ \
  .coverage

# Remove nested __pycache__ and *.pyc
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
find . -type f -name '*.pyc' -delete

# Optional: Playwright artifacts (commented out by default)
# rm -rf playwright/.cache ms-playwright

echo "Cleaned: caches/coverage/pyc"
