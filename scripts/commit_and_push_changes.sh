#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <commit-message> <file-pattern> [file-pattern ...]" >&2
  exit 2
fi

MESSAGE="$1"
shift

# Ensure no stale git rebase/merge directories are blockading the repository
if [ -d ".git/rebase-merge" ] || [ -d ".git/rebase-apply" ]; then
  echo "Stale git rebase state detected; refusing to discard worktree changes." >&2
  git rebase --abort || true
  exit 1
fi

# GitHub Actions bot identity by default; local callers may override via env.
git config --global user.name "${GIT_COMMIT_USER_NAME:-github-actions[bot]}"
git config --global user.email "${GIT_COMMIT_USER_EMAIL:-41898282+github-actions[bot]@users.noreply.github.com}"

# Save original file targets
TARGET_PATTERNS=("$@")

# Stage only the intended files. Missing globs are ignored so workflows can share
# this helper even when a report file is unchanged or absent.
for pattern in "${TARGET_PATTERNS[@]}"; do
  git add -- "$pattern" 2>/dev/null || true
done

if git diff --cached --quiet; then
  echo "No matching changes to commit."
  exit 0
fi

git commit -m "$MESSAGE"

# Self-Healing Push Loop with Auto-Reapply
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

  echo "Rebase conflict detected on generated data. Reapplying only requested files..." >&2
  git rebase --abort || true
  git fetch origin main
  # Keep the generated worktree intact while moving the branch base. Resetting
  # only the index avoids deleting unrelated files during conflict recovery.
  git reset --soft origin/main
  git reset -- .
  for pattern in "${TARGET_PATTERNS[@]}"; do
    git add -- "$pattern" 2>/dev/null || true
  done
  git commit -m "$MESSAGE (auto-reapplied)" || true

  if git push origin HEAD:main; then
    echo "Self-healing push succeeded!"
    exit 0
  fi
done

echo "Failed to push after 5 attempts." >&2
if [ "${CCTV_COMMIT_PUSH_SOFT_FAIL:-1}" = "1" ]; then
  echo "Soft-fail mode enabled: generated-data push failure is treated as a warning." >&2
  exit 0
fi
exit 1
