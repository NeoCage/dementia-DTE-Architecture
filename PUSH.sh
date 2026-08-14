#!/usr/bin/env bash
# Run this from your own terminal, in the repo folder.
# Your credential stays on your machine and never enters a chat transcript.
set -euo pipefail

REPO_URL="https://github.com/NeoCage/dementia-DTE-Architecture.git"

echo "==> repo state"
git log --oneline | head -3
git status --short || true

echo "==> adding remote (skip if it already exists)"
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
git remote -v

echo "==> pushing"
git branch -M main
git push -u origin main

echo "==> done. verify:"
echo "    $REPO_URL"
