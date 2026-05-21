#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <commit-message> <file-pattern> [file-pattern ...]" >&2
  exit 2
fi

MESSAGE="$1"
shift

# GitHub Actions bot identity by default; local callers may override via env.
git config --global user.name "${GIT_COMMIT_USER_NAME:-github-actions[bot]}"
git config --global user.email "${GIT_COMMIT_USER_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"

# Stage only the intended files. Missing globs are ignored so workflows can share
# this helper even when a report file is unchanged or absent.
for pattern in "$@"; do
  git add -- "$pattern" 2>/dev/null || true
done

if git diff --cached --quiet; then
  echo "No matching changes to commit."
  exit 0
fi

git commit -m "$MESSAGE"

# Workflows in this repo often update generated data close together. Serialize at
# the workflow level first, then still retry a normal push in case a human/Codex
# commit landed while the job was running.
for attempt in 1 2 3 4 5; do
  echo "Push attempt ${attempt}/5..."
  if git push origin HEAD:main; then
    echo "Push succeeded."
    exit 0
  fi

  echo "Push rejected; rebasing on latest origin/main before retry..."
  git fetch origin main
  if git rebase origin/main; then
    continue
  fi

  echo "Rebase conflict while pushing generated data." >&2
  echo "Leaving the workflow failed instead of force-pushing or dropping data." >&2
  git rebase --abort || true
  exit 1
done

echo "Failed to push after 5 attempts." >&2
exit 1
