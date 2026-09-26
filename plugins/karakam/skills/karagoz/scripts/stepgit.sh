#!/usr/bin/env bash
# Git operations on exactly one step's files_touched, run from the tree the
# step works in (the project root, or its worktree).
#
#   stepgit.sh commit "<message>" <path>...
#       Stage every change among <path>s — new, modified or deleted files — and
#       commit only those. Listed paths that don't exist and never did are
#       skipped (plain `git add` aborts on them). On failure nothing stays staged.
#   stepgit.sh revert <path>...
#       Put <path>s back exactly as they are in HEAD: undo edits, restore
#       deletions, remove files the step created. Plain `git checkout -- <paths>`
#       reverts nothing at all if one listed path is a new file.
set -uo pipefail

die() { echo "stepgit: $*" >&2; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "not inside a git work tree"

cmd=${1:-}; shift || true
case "$cmd" in
  commit)
    [ $# -ge 2 ] || die 'usage: stepgit.sh commit "<message>" <path>...'
    msg=$1; shift
    paths=()
    for p in "$@"; do
      if [ -e "$p" ] || git ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
        paths+=("$p")
      fi
    done
    [ ${#paths[@]} -gt 0 ] || { echo "stepgit: none of the paths exist; nothing to commit"; exit 0; }
    git add -A -- "${paths[@]}" || die "git add failed"
    if git diff --cached --quiet -- "${paths[@]}"; then
      echo "stepgit: no changes in these paths; nothing to commit"; exit 0
    fi
    if ! git commit -q -m "$msg" -- "${paths[@]}"; then
      git reset -q -- "${paths[@]}" 2>/dev/null
      die "git commit failed (hook, identity or permissions) — the step is not checkpointed"
    fi
    echo "stepgit: committed $(git rev-parse --short HEAD) — $msg"
    ;;
  revert)
    [ $# -ge 1 ] || die "usage: stepgit.sh revert <path>..."
    git reset -q -- "$@" 2>/dev/null || true            # unstage whatever is staged
    git ls-tree -r -z --name-only HEAD -- "$@" | xargs -0 -r git checkout HEAD -- \
      || die "restoring tracked files failed"
    git clean -fq -- "$@" || die "removing new files failed"
    echo "stepgit: reverted $# path(s) to HEAD"
    ;;
  *) die 'usage: stepgit.sh commit "<message>" <path>... | stepgit.sh revert <path>...' ;;
esac
